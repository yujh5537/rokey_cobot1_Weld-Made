"""MQTT/asyncio boundary and request lifecycle; no ROS control here."""
import asyncio
import json
import logging
import time
from collections import OrderedDict
from uuid import uuid4

log = logging.getLogger(__name__)
TOPICS = ['robot/#', 'scan/#', 'contact/#', 'safety/#', 'cmd/ack', 'hb/ros', 'conn/ros']
TERMINAL = {'completed', 'failed', 'rejected'}


def now_ms():
    return time.time_ns() // 1_000_000


class LiveHub:
    def __init__(self, ack_timeout_s=5.0):
        self.ack_timeout_s = ack_timeout_s  # Web-only configurable wait, not robot policy.
        self.connected = False
        self.clients = set()
        self.latest = {}
        self.commands = OrderedDict()

    def emit(self, topic, payload, **metadata):
        event = dict(topic=topic, payload=payload, received_at_ms=now_ms(), **metadata)
        for queue in tuple(self.clients):
            if queue.full():
                # Force reconnect/resnapshot instead of silently dropping control events.
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(None)
                self.clients.discard(queue)
            else:
                queue.put_nowait(event)

    def connection(self, connected):
        self.connected = connected
        if not connected:
            for command in self.commands.values():
                if command['status'] not in TERMINAL:
                    command['status'] = 'unknown'
                    self.emit('web/command', dict(command))
        self.emit('web/connection', {'mqtt_connected': connected})

    def receive(self, topic, raw, retained=False):
        try:
            payload = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
            if not isinstance(payload, dict) or payload.get('schema_version') != '0.1':
                raise ValueError('unsupported envelope')
        except (ValueError, UnicodeError, TypeError):
            log.warning('Ignoring invalid MQTT JSON: %s', topic)
            return
        if topic in ('cmd/ack', 'scan/command_result'):
            field = 'accepted' if topic == 'cmd/ack' else 'success'
            if retained or type(payload.get(field)) is not bool:
                return
            command = self.commands.get(payload.get('request_id'))
            if command and command['status'] not in TERMINAL:
                if topic == 'cmd/ack':
                    command['ack'] = payload
                    command['status'] = 'accepted' if payload['accepted'] else 'rejected'
                else:
                    command['result'] = payload
                    command['status'] = 'completed' if payload['success'] else 'failed'
                self.emit('web/command', dict(command))
        if topic in ('robot/status', 'scan/state', 'safety/status', 'conn/ros', 'robot/sample'):
            self.latest[topic] = dict(topic=topic, payload=payload, received_at_ms=now_ms(), retained=retained)
        self.emit(topic, payload, retained=retained)

    def begin(self, action, session_id='', scan_id='', payload=None):
        # Never evict unresolved commands to make space.
        if len(self.commands) >= 1000:
            for key, value in tuple(self.commands.items()):
                if value['status'] in TERMINAL:
                    del self.commands[key]
                    break
            else:
                raise OverflowError('command history full; unresolved requests remain')
        request_id = str(uuid4())
        message = dict(schema_version='0.1', request_id=request_id,
                       session_id=session_id, timestamp_ms=now_ms(), payload=payload or {})
        if action == 'resume':
            message['scan_id'] = scan_id
        command = dict(request_id=request_id, action=action, status='pending',
                       timestamp_ms=message['timestamp_ms'], ack=None, result=None)
        self.commands[request_id] = command
        return message, command

    def expire(self):
        for command in self.commands.values():
            if command['status'] == 'pending' and now_ms() - command['timestamp_ms'] >= self.ack_timeout_s * 1000:
                command['status'] = 'unknown'
                self.emit('web/command', dict(command))


async def timeout_loop(hub):
    while True:
        await asyncio.sleep(0.25)
        hub.expire()
