#!/usr/bin/env python3
"""Local virtual-only top-edge weaving runner. HTTP control on localhost:8766."""
import argparse
import json
import math
from pathlib import Path
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, qos_profile_sensor_data
from scipy.spatial.transform import Rotation
import yaml
from contact_scan_interfaces.action import ExecuteMotion
from contact_scan_interfaces.msg import RobotSample, SafetyStatus, ScanState, WeldState
from apply_virtual_tcp import require_virtual_driver


def plan(shape, origin, cfg):
    for key in ('pitch_m', 'standoff_m'):
        if not math.isfinite(cfg[key]) or cfg[key] <= 0:
            raise ValueError(f'{key}는 양수여야 합니다')
    if not math.isfinite(cfg['amplitude_m']) or not 0 <= cfg['amplitude_m'] <= cfg['standoff_m']:
        raise ValueError('위빙 진폭은 0 이상 스탠드오프 이하여야 합니다')
    if not math.isfinite(cfg['tilt_deg']) or not 0 <= cfg['tilt_deg'] <= 45:
        raise ValueError('기울기는 0~45도 범위여야 합니다')
    if not (shape['success'] and shape['box_valid'] and shape['frame_id'] == 'workpiece_fixture'):
        raise ValueError('유효한 작업대 좌표 스캔 결과가 필요합니다')
    lines = []
    for edge in shape['edges'][:4]:
        start, end = np.array(edge['start']) + origin, np.array(edge['end']) + origin
        length = np.linalg.norm(end - start)
        if not np.isfinite([*start, *end]).all() or length <= 0:
            raise ValueError('잘못된 모서리 좌표')
        tangent = (end - start) / length
        outward = np.cross(tangent, [0, 0, 1])
        angle = math.radians(cfg['tilt_deg'])
        direction = -np.array([0, 0, math.cos(angle)]) - math.sin(angle) * outward
        weave = np.cross(tangent, direction)
        weave /= np.linalg.norm(weave)
        quaternion = Rotation.from_matrix(np.column_stack((weave, np.cross(direction, weave), direction))).as_quat().tolist()
        if cfg['tilt_deg'] == 0:
            quaternion = cfg.get('vertical_quaternion', [1.0, 0.0, 0.0, 0.0])
        offset = -direction * cfg['standoff_m']
        count = math.ceil(length / cfg['pitch_m'])
        if count > 99:
            raise ValueError('한 변의 경유점은 100개 이하로 설정하세요')
        points = [start + tangent * min(k * cfg['pitch_m'], length) + offset + weave *
                  (0 if k in (0, count) else cfg['amplitude_m'] * (-1)**k)
                  for k in range(count + 1)]
        lines.append(dict(points=points, q=quaternion, offset=offset, z=float(start[2])))
    if len(lines) != 4:
        raise ValueError('윗면 모서리 4개가 필요합니다')
    return lines


class Preview(Node):
    def __init__(self, args):
        super().__init__('virtual_weld_preview')
        self.args = args
        self.cfg = yaml.safe_load(args.settings.read_text())
        scan_params = yaml.safe_load(args.config.read_text())['scan_manager']['ros__parameters']
        self.origin = np.array(scan_params['base_to_fixture'])
        self.cfg['vertical_quaternion'] = scan_params['search_origin_pose'][3:]
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.active = False
        self.sample = self.safety = self.scan = None
        self.seen = {}
        self.goal = None
        self.offset = np.zeros(3)
        self.surface_z = 0
        self.state = dict(phase='IDLE', line=0, progress=0, run_id='', beads=[], arc=False, detail='')
        self.client = ActionClient(self, ExecuteMotion, '/robot/execute_motion')
        state_qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.pub = self.create_publisher(WeldState, '/weld/state', state_qos)
        self.create_subscription(RobotSample, '/robot/sample', self.on_sample, qos_profile_sensor_data)
        self.create_subscription(SafetyStatus, '/safety/status', lambda m: self.receive('safety', m), state_qos)
        self.create_subscription(ScanState, '/scan/state', lambda m: self.receive('scan', m), state_qos)
        self.create_timer(0.2, self.publish)

    def receive(self, key, value):
        setattr(self, key, value)
        self.seen[key] = time.monotonic()

    def on_sample(self, msg):
        self.receive('sample', msg)
        with self.lock:
            if self.state['arc'] and msg.valid:
                p = np.array([msg.pose.position.x, msg.pose.position.y, msg.pose.position.z]) - self.offset
                p[2] = self.surface_z + 0.0003
                beads = self.state['beads']
                if not beads or np.linalg.norm(p - np.array(beads[-1][:3])) > 0.0004:
                    beads.append([*p.tolist(), self.state['line']])
                    self.state['beads'] = beads[-5000:]

    def publish(self):
        with self.lock:
            m = WeldState()
            m.stamp = self.get_clock().now().to_msg()
            m.phase = getattr(WeldState, 'PHASE_' + self.state['phase'])
            m.weld_id = self.state['run_id']
            m.scan_id = self.state.get('scan_id', '')
            m.line_index = self.state['line']
            m.line_total = 4
            m.line_progress = float(self.state['progress'])
            self.pub.publish(m)

    def ready(self):
        now = time.monotonic()
        if any(now - self.seen.get(k, 0) > 3 for k in ('sample', 'safety', 'scan')):
            raise RuntimeError('로봇·스캔·안전 상태가 최신이 아닙니다')
        if not self.sample.valid or self.safety.latched or self.safety.stop_required:
            raise RuntimeError('로봇 또는 안전 상태를 확인하세요')
        if self.scan.phase not in (0, 5, 6, 8):
            raise RuntimeError('스캔 동작이 진행 중입니다')

    def start(self, scan_id):
        require_virtual_driver()
        with self.lock:
            if self.active:
                raise RuntimeError('용접이 이미 진행 중입니다')
            self.ready()
            if not scan_id or Path(scan_id).name != scan_id:
                raise ValueError('화면의 성공한 scan_id가 필요합니다')
            result = json.loads((self.args.results / scan_id / 'result.json').read_text())
            lines = plan(result['shape'], self.origin, self.cfg)
            self.stop.clear()
            self.active = True
            self.state = dict(phase='PREPARING', line=0, progress=0, run_id=str(time.time_ns()),
                              scan_id=scan_id, beads=[], arc=False, detail='')
            threading.Thread(target=self.run, args=(lines,), daemon=True).start()

    def wait(self, future, timeout=45):
        deadline = time.monotonic() + timeout
        while not future.done():
            if self.active and self.goal and not self.stop.is_set():
                try:
                    self.ready()
                except RuntimeError:
                    self.stop.set()
                    self.state['arc'] = False
                    self.goal.cancel_goal_async()
            if time.monotonic() > deadline:
                if self.goal:
                    self.goal.cancel_goal_async()
                raise RuntimeError('가상 로봇 응답 시간 초과')
            time.sleep(0.02)
        return future.result()

    def move(self, position, quaternion, speed, home=False):
        if self.stop.is_set():
            raise InterruptedError('사용자가 중지했습니다')
        self.ready()
        if not self.client.wait_for_server(timeout_sec=3):
            raise RuntimeError('가상 로봇 action 연결 실패')
        g = ExecuteMotion.Goal()
        g.scan_id = 'virtual-weld-' + self.state['run_id']
        g.motion_id = int(time.time_ns() % 4000000000)
        g.operation = 4 if home else 1
        g.frame_id = 'base_link'
        g.speed = speed
        g.timeout.sec = 40
        g.target.position.x, g.target.position.y, g.target.position.z = map(float, position)
        g.target.orientation.x, g.target.orientation.y, g.target.orientation.z, g.target.orientation.w = map(float, quaternion)
        self.goal = self.wait(self.client.send_goal_async(g))
        if not self.goal.accepted:
            raise RuntimeError('로봇이 이동 요청을 거절했습니다')
        if self.stop.is_set():
            self.goal.cancel_goal_async()
        result = self.wait(self.goal.get_result_async()).result
        self.goal = None
        if self.stop.is_set():
            raise InterruptedError('사용자가 중지했습니다')
        if result.reason_code or result.reason:
            raise RuntimeError(f'이동 실패: {result.reason_code} {result.detail}')

    def run(self, lines):
        try:
            safe = max(line['z'] for line in lines) + self.cfg['clearance_m']
            p = self.sample.pose.position
            q = self.sample.pose.orientation
            if p.z < safe - self.cfg['position_tolerance_m']:
                rotation = Rotation.from_quat([q.x, q.y, q.z, q.w])
                retreat = np.array([p.x, p.y, p.z]) - rotation.apply([0, 0, self.cfg['retreat_m']])
                self.move(retreat, [q.x, q.y, q.z, q.w], self.cfg['approach_speed_mps'])
                p = self.sample.pose.position
                self.move([p.x, p.y, max(p.z, safe)], [q.x, q.y, q.z, q.w], self.cfg['travel_speed_mps'])
            for i, line in enumerate(lines):
                self.state.update(phase='APPROACH', line=i, progress=0, arc=False)
                points, q = line['points'], line['q']
                first = points[0]
                self.move([first[0], first[1], safe], q, self.cfg['travel_speed_mps'])
                self.move(first, q, self.cfg['approach_speed_mps'])
                self.offset, self.surface_z = line['offset'], line['z']
                self.state.update(phase='WELDING', arc=True)
                for k, point in enumerate(points[1:], 1):
                    self.move(point, q, self.cfg['weld_speed_mps'])
                    self.state['progress'] = k / (len(points) - 1)
                self.state.update(phase='RETREAT', arc=False)
                last = points[-1]
                self.move([last[0], last[1], safe], q, self.cfg['approach_speed_mps'])
            self.state['phase'] = 'HOMING'
            self.move([0, 0, 0], [0, 0, 0, 1], self.cfg['travel_speed_mps'], home=True)
            self.state['phase'] = 'DONE'
        except InterruptedError as exc:
            self.state.update(phase='STOPPED', detail=str(exc))
        except Exception as exc:
            self.state.update(phase='ERROR', detail=str(exc))
            self.get_logger().error(str(exc))
        finally:
            self.state['arc'] = False
            self.active = False

    def cancel(self):
        self.stop.set()
        self.state['arc'] = False
        if self.active:
            self.state['phase'] = 'STOPPING'
        if self.goal:
            self.goal.cancel_goal_async()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=Path('/tmp/weld-made-db-sim/sim.yaml'))
    parser.add_argument('--results', type=Path, default=Path('/tmp/weld-made-db-sim/results'))
    parser.add_argument('--settings', type=Path, default=Path(__file__).with_name('weld_preview.yaml'))
    args = parser.parse_args()
    require_virtual_driver()
    rclpy.init()
    node = Preview(args)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def reply(self, code, value):
            data = json.dumps(value, allow_nan=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)
        def do_GET(self):
            with node.lock:
                self.reply(200, {**node.state, 'active': node.active})
        def do_POST(self):
            try:
                if self.headers.get_content_type() != 'application/json':
                    raise ValueError('JSON 요청이 필요합니다')
                if self.path == '/start':
                    body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
                    node.start(body.get('scan_id'))
                elif self.path == '/stop':
                    node.cancel()
                else:
                    raise ValueError('알 수 없는 명령')
                self.reply(200, {'ok': True})
            except Exception as exc:
                self.reply(409, {'detail': str(exc)})
    server = ThreadingHTTPServer(('127.0.0.1', 8766), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        rclpy.spin(node)
    finally:
        node.cancel()
        server.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
