#!/usr/bin/env python3
"""Publish the DB fixture and scan trail as RViz markers."""

import argparse
from pathlib import Path

import rclpy
import yaml
from contact_scan_interfaces.msg import RobotSample, ScanState
from geometry_msgs.msg import Point
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from visualization_msgs.msg import Marker, MarkerArray


class Scene(Node):
    def __init__(self, config_path):
        super().__init__("db_sim_scene")
        params = yaml.safe_load(config_path.read_text(encoding="utf-8"))[
            "contact_detector"
        ]["ros__parameters"]
        self.origin = params["sim_box_origin_m"]
        self.size = params["sim_box_size_m"]
        self.points = []
        self.scan_id = None
        self.publisher = self.create_publisher(MarkerArray, "/db_sim/markers", 10)
        self.create_subscription(RobotSample, "/robot/sample", self.on_sample,
                                 qos_profile_sensor_data)
        self.create_subscription(ScanState, "/scan/state", self.on_state, 10)
        self.create_timer(0.2, self.publish)

    def on_state(self, message):
        if message.scan_id and message.scan_id != self.scan_id:
            self.scan_id = message.scan_id
            self.points.clear()

    def on_sample(self, message):
        if not message.valid or message.operation not in (
            RobotSample.OP_MOVE_TO, RobotSample.OP_DESCEND, RobotSample.OP_SLIDE
        ):
            return
        position = message.pose.position
        if not self.points or sum(
            (getattr(position, axis) - getattr(self.points[-1], axis)) ** 2
            for axis in ("x", "y", "z")
        ) > 0.0005 ** 2:
            self.points.append(position)
            self.points = self.points[-10000:]

    def marker(self, marker_id, marker_type):
        marker = Marker()
        marker.header.frame_id = "base_link"
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = "db_sim"
        marker.id = marker_id
        marker.type = marker_type
        marker.action = Marker.ADD
        marker.pose.orientation.w = 1.0
        return marker

    def publish(self):
        box = self.marker(0, Marker.CUBE)
        box.pose.position = Point(
            x=self.origin[0], y=self.origin[1],
            z=self.origin[2] + self.size[2] / 2,
        )
        box.scale.x, box.scale.y, box.scale.z = self.size
        box.color.r, box.color.g, box.color.b, box.color.a = 0.1, 0.7, 0.9, 0.65

        label = self.marker(2, Marker.TEXT_VIEW_FACING)
        label.pose.position = Point(
            x=self.origin[0], y=self.origin[1],
            z=self.origin[2] + self.size[2] + 0.14,
        )
        label.scale.z = 0.025
        label.color.r = label.color.g = label.color.b = label.color.a = 1.0
        label.text = "DB scan fixture\n" + " x ".join(
            f"{dimension * 1000:.2f}" for dimension in self.size
        ) + " mm"

        markers = [box, label]
        if len(self.points) > 1:
            trail = self.marker(1, Marker.LINE_STRIP)
            trail.scale.x = 0.002
            trail.color.r, trail.color.g, trail.color.a = 1.0, 0.6, 1.0
            trail.points = self.points
            markers.append(trail)
        else:
            delete_trail = self.marker(1, Marker.LINE_STRIP)
            delete_trail.action = Marker.DELETE
            markers.append(delete_trail)
        self.publisher.publish(MarkerArray(markers=markers))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    rclpy.init()
    node = Scene(args.config)
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
