import json
import math
import mimetypes
import os
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Event
from threading import Lock
from threading import Thread
import time
from urllib.parse import unquote
from urllib.parse import urlparse

from ament_index_python.packages import get_package_share_directory
import cv2
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy
from rclpy.qos import HistoryPolicy
from rclpy.qos import QoSProfile
from rclpy.qos import ReliabilityPolicy
from sensor_msgs.msg import BatteryState
from sensor_msgs.msg import Image
from std_msgs.msg import Bool
from std_msgs.msg import Float32
from std_msgs.msg import String


def yaw_from_quaternion(q):
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


def finite_float(value):
    if value is None:
        return None
    value = float(value)
    if math.isfinite(value):
        return value
    return None


def battery_status_label(status):
    labels = {
        BatteryState.POWER_SUPPLY_STATUS_UNKNOWN: "unknown",
        BatteryState.POWER_SUPPLY_STATUS_CHARGING: "charging",
        BatteryState.POWER_SUPPLY_STATUS_DISCHARGING: "discharging",
        BatteryState.POWER_SUPPLY_STATUS_NOT_CHARGING: "not charging",
        BatteryState.POWER_SUPPLY_STATUS_FULL: "full",
    }
    return labels.get(int(status), "unknown")


def percent_from_battery(msg):
    percentage = finite_float(msg.percentage)
    if percentage is None:
        return None
    if percentage <= 1.0:
        return percentage * 100.0
    return percentage


def compact_stage(text):
    if not text:
        return None
    return str(text).split(":", 1)[0].strip()


def classify_task(mp_status, sim_status, leader_task, cargo_state):
    raw = mp_status or sim_status or leader_task or ""
    text = str(raw)
    upper = text.upper()
    cargo_upper = str(cargo_state or "").upper()

    if any(key in upper for key in ("BASE_APPROACH", "DEPTH_APPROACH", "APPROACH", "ALIGN")):
        approach_label = "접근 중"
        approach_active = True
    elif any(key in upper for key in ("DETECTED", "READY", "WAITING")):
        approach_label = "대기/탐지"
        approach_active = False
    elif any(key in upper for key in ("DONE", "PLACED", "LOADED")):
        approach_label = "접근 완료"
        approach_active = False
    else:
        approach_label = compact_stage(raw) or "-"
        approach_active = False

    if cargo_upper in ("GRASPED", "LOADING"):
        grasp_label = "파지 중"
        grasp_ok = True
    elif cargo_upper == "LOADED":
        grasp_label = "적재 완료"
        grasp_ok = True
    elif any(key in upper for key in ("PICK", "GRASP", "GRIPPER")):
        grasp_label = "파지 동작"
        grasp_ok = True
    elif cargo_upper == "EMPTY":
        grasp_label = "비어 있음"
        grasp_ok = False
    else:
        grasp_label = cargo_state or "-"
        grasp_ok = None

    return {
        "raw_status": text or None,
        "stage": compact_stage(text),
        "approach_label": approach_label,
        "approach_active": approach_active,
        "grasp_label": grasp_label,
        "grasp_ok": grasp_ok,
    }


class VideoStreamBuffer:
    def __init__(self, key, label, topic):
        self.key = key
        self.label = label
        self.topic = topic
        self._lock = Lock()
        self._event = Event()
        self._jpeg = None
        self._stamp = None
        self._frame_count = 0
        self._last_error = None

    def update(self, jpeg):
        with self._lock:
            self._jpeg = bytes(jpeg)
            self._stamp = time.monotonic()
            self._frame_count += 1
            self._last_error = None
            self._event.set()

    def fail(self, error):
        with self._lock:
            self._last_error = str(error)

    def latest(self):
        with self._lock:
            return self._jpeg, self._stamp, self._frame_count, self._last_error

    def wait(self, timeout):
        self._event.wait(timeout)
        self._event.clear()

    def snapshot(self, now_monotonic):
        with self._lock:
            age = None if self._stamp is None else max(0.0, now_monotonic - self._stamp)
            return {
                "key": self.key,
                "label": self.label,
                "topic": self.topic,
                "available": self._jpeg is not None,
                "age_s": age,
                "frame_count": self._frame_count,
                "last_error": self._last_error,
                "stream_url": f"/stream/{self.key}",
                "snapshot_url": f"/frame/{self.key}.jpg",
            }


def image_to_bgr(msg):
    encoding = str(msg.encoding or "").lower()
    channels = max(1, int(msg.step / msg.width)) if msg.width else 1

    if encoding in ("rgb8", "bgr8"):
        image = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, 3))
        if encoding == "rgb8":
            return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        return image.copy()

    if encoding in ("mono8", "8uc1"):
        image = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width))
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    if encoding in ("16uc1", "mono16"):
        image = np.frombuffer(msg.data, dtype=np.uint16).reshape((msg.height, msg.width))
        valid = image[image > 0]
        if valid.size:
            near = np.percentile(valid, 5)
            far = np.percentile(valid, 95)
            if far <= near:
                far = near + 1.0
            scaled = np.clip((image.astype(np.float32) - near) * 255.0 / (far - near), 0, 255)
        else:
            scaled = np.zeros_like(image, dtype=np.float32)
        depth_u8 = scaled.astype(np.uint8)
        return cv2.applyColorMap(depth_u8, cv2.COLORMAP_TURBO)

    if encoding in ("yuv422", "yuyv", "yuv422_yuy2"):
        image = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, 2))
        return cv2.cvtColor(image, cv2.COLOR_YUV2BGR_YUY2)

    if channels >= 3:
        image = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, channels))
        return image[:, :, :3].copy()

    image = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width))
    return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)


class PlatooningTabletMonitor(Node):
    def __init__(self):
        super().__init__("platooning_tablet_monitor")

        self.declare_parameter("host", "0.0.0.0")
        self.declare_parameter("port", 8080)
        self.declare_parameter("simulation_domain_id", 25)
        self.declare_parameter("follower_domain_id", 73)
        self.declare_parameter("target_spacing_m", 0.47)
        self.declare_parameter("heartbeat_timeout_s", 1.5)
        self.declare_parameter("follower_timeout_s", 2.0)
        self.declare_parameter("web_root", "")

        self.declare_parameter("leader_task_state_topic", "/leader/task_state")
        self.declare_parameter("leader_cargo_state_topic", "/leader/cargo_state")
        self.declare_parameter("leader_follower_enable_topic", "/leader/follower_enable")
        self.declare_parameter("leader_platoon_mode_topic", "/leader/platoon_mode")
        self.declare_parameter("leader_heartbeat_topic", "/leader/heartbeat")
        self.declare_parameter("leader_cmd_vel_topic", "/leader/cmd_vel")
        self.declare_parameter("leader_odom_topic", "/leader/odom")
        self.declare_parameter("leader_battery_state_topic", "/leader/battery_state")
        self.declare_parameter("mp_control_status_topic", "/mp_control/status")
        self.declare_parameter("sim_pick_place_status_topic", "/mp_control/pick_place_status")
        self.declare_parameter("cargo_events_topic", "/cargo/events")
        self.declare_parameter("cargo_current_id_topic", "/cargo/current_id")

        self.declare_parameter("follower_status_topic", "/follower/status")
        self.declare_parameter("follower_safety_state_topic", "/follower/safety_state")
        self.declare_parameter("follower_cmd_vel_topic", "/follower/cmd_vel")
        self.declare_parameter("follower_odom_topic", "/follower/odom")
        self.declare_parameter("follower_battery_state_topic", "/follower/battery_state")
        self.declare_parameter("follower_distance_error_topic", "/follower/distance_error")
        self.declare_parameter("follower_target_visible_topic", "/follower/target_visible")
        self.declare_parameter("follower_target_distance_topic", "/follower/target_distance")
        self.declare_parameter("follower_target_offset_x_topic", "/follower/target_offset_x")
        self.declare_parameter("enable_video_streams", True)
        self.declare_parameter("video_jpeg_quality", 75)
        self.declare_parameter("leader_debug_image_topic", "/hybrid_csrt_ibvs/debug_image")
        self.declare_parameter("eef_debug_image_topic", "/eef_camera/image_raw")
        self.declare_parameter("leader_raw_image_topic", "/camera/color/image_raw")
        self.declare_parameter("leader_depth_image_topic", "/camera/depth/image_raw")
        self.declare_parameter("eef_raw_image_topic", "/eef_camera/image_raw")
        self.declare_parameter("follower_raw_image_topic", "/follower/camera/image_raw")

        self._lock = Lock()
        self._values = {}
        self._cargo_items = OrderedDict()
        self._cargo_events = []
        self._last_cargo_event = None
        self._video_buffers = {}
        self._server = None
        self._server_thread = None

        state_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        live_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )

        self.create_subscription(
            String,
            self._str_param("leader_task_state_topic"),
            lambda msg: self._set_value("leader_task_state", msg.data),
            state_qos,
        )
        self.create_subscription(
            String,
            self._str_param("leader_cargo_state_topic"),
            lambda msg: self._set_value("leader_cargo_state", msg.data),
            state_qos,
        )
        self.create_subscription(
            Bool,
            self._str_param("leader_follower_enable_topic"),
            lambda msg: self._set_value("leader_follower_enable", bool(msg.data)),
            state_qos,
        )
        self.create_subscription(
            String,
            self._str_param("leader_platoon_mode_topic"),
            lambda msg: self._set_value("leader_platoon_mode", msg.data),
            state_qos,
        )
        self.create_subscription(
            Bool,
            self._str_param("leader_heartbeat_topic"),
            lambda msg: self._set_value("leader_heartbeat", bool(msg.data)),
            live_qos,
        )
        self.create_subscription(
            Twist,
            self._str_param("leader_cmd_vel_topic"),
            lambda msg: self._cmd_vel_callback("leader_cmd_vel", msg),
            live_qos,
        )
        self.create_subscription(
            Odometry,
            self._str_param("leader_odom_topic"),
            lambda msg: self._odom_callback("leader_odom", msg),
            live_qos,
        )
        self.create_subscription(
            BatteryState,
            self._str_param("leader_battery_state_topic"),
            lambda msg: self._battery_callback("leader_battery", msg),
            live_qos,
        )
        self.create_subscription(
            String,
            self._str_param("mp_control_status_topic"),
            lambda msg: self._set_value("mp_control_status", msg.data),
            state_qos,
        )
        self.create_subscription(
            String,
            self._str_param("sim_pick_place_status_topic"),
            lambda msg: self._set_value("sim_pick_place_status", msg.data),
            live_qos,
        )
        self.create_subscription(
            String,
            self._str_param("cargo_events_topic"),
            self._cargo_event_callback,
            live_qos,
        )
        self.create_subscription(
            String,
            self._str_param("cargo_current_id_topic"),
            self._cargo_current_id_callback,
            state_qos,
        )
        self.create_subscription(
            String,
            self._str_param("follower_status_topic"),
            lambda msg: self._set_value("follower_status", msg.data),
            live_qos,
        )
        self.create_subscription(
            String,
            self._str_param("follower_safety_state_topic"),
            lambda msg: self._set_value("follower_safety_state", msg.data),
            live_qos,
        )
        self.create_subscription(
            Twist,
            self._str_param("follower_cmd_vel_topic"),
            lambda msg: self._cmd_vel_callback("follower_cmd_vel", msg),
            live_qos,
        )
        self.create_subscription(
            Odometry,
            self._str_param("follower_odom_topic"),
            lambda msg: self._odom_callback("follower_odom", msg),
            live_qos,
        )
        self.create_subscription(
            BatteryState,
            self._str_param("follower_battery_state_topic"),
            lambda msg: self._battery_callback("follower_battery", msg),
            live_qos,
        )
        self.create_subscription(
            Float32,
            self._str_param("follower_distance_error_topic"),
            lambda msg: self._set_value("follower_distance_error_m", finite_float(msg.data)),
            live_qos,
        )
        self.create_subscription(
            Bool,
            self._str_param("follower_target_visible_topic"),
            lambda msg: self._set_value("follower_target_visible", bool(msg.data)),
            live_qos,
        )
        self.create_subscription(
            Float32,
            self._str_param("follower_target_distance_topic"),
            lambda msg: self._set_value("follower_target_distance_m", finite_float(msg.data)),
            live_qos,
        )
        self.create_subscription(
            Float32,
            self._str_param("follower_target_offset_x_topic"),
            lambda msg: self._set_value("follower_target_offset_x", finite_float(msg.data)),
            live_qos,
        )
        if bool(self.get_parameter("enable_video_streams").value):
            self._create_video_subscriptions(live_qos)

        self._start_http_server()

    def _str_param(self, name):
        return str(self.get_parameter(name).value)

    def _float_param(self, name):
        return float(self.get_parameter(name).value)

    def _set_value(self, key, value):
        with self._lock:
            self._values[key] = {
                "value": value,
                "stamp": time.monotonic(),
            }

    def _create_video_subscriptions(self, qos):
        stream_specs = (
            ("leader_debug", "작업 인식", self._str_param("leader_debug_image_topic")),
            ("eef_debug", "그리퍼 근접", self._str_param("eef_debug_image_topic")),
            ("leader_raw", "전방 원본", self._str_param("leader_raw_image_topic")),
            ("leader_depth", "전방 Depth", self._str_param("leader_depth_image_topic")),
            ("eef_raw", "EEF 원본", self._str_param("eef_raw_image_topic")),
            ("follower_raw", "팔로워 원본", self._str_param("follower_raw_image_topic")),
        )
        for key, label, topic in stream_specs:
            if not topic:
                continue
            buffer = VideoStreamBuffer(key, label, topic)
            self._video_buffers[key] = buffer
            self.create_subscription(
                Image,
                topic,
                lambda msg, stream_key=key: self._image_callback(stream_key, msg),
                qos,
            )
        self.get_logger().info(
            "video streams enabled: " +
            ", ".join(f"{key}={buffer.topic}" for key, buffer in self._video_buffers.items())
        )

    def _image_callback(self, key, msg):
        buffer = self._video_buffers.get(key)
        if buffer is None:
            return
        try:
            frame = image_to_bgr(msg)
            ok, encoded = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), int(self.get_parameter("video_jpeg_quality").value)],
            )
            if not ok:
                raise RuntimeError("jpeg encode failed")
            buffer.update(encoded.tobytes())
        except Exception as exc:  # noqa: BLE001 - keep stream fault isolated from ROS callbacks.
            buffer.fail(exc)

    def _twist_payload(self, twist):
        linear_x = finite_float(twist.linear.x)
        linear_y = finite_float(twist.linear.y)
        angular_z = finite_float(twist.angular.z)
        speed = math.hypot(float(linear_x or 0.0), float(linear_y or 0.0))
        return {
            "linear_x": linear_x,
            "linear_y": linear_y,
            "speed_mps": finite_float(speed),
            "angular_z": angular_z,
        }

    def _cmd_vel_callback(self, key, msg):
        self._set_value(key, self._twist_payload(msg))

    def _odom_callback(self, key, msg):
        pose = msg.pose.pose
        payload = self._twist_payload(msg.twist.twist)
        payload.update(
            {
                "x": finite_float(pose.position.x),
                "y": finite_float(pose.position.y),
                "yaw": finite_float(yaw_from_quaternion(pose.orientation)),
            }
        )
        self._set_value(key, payload)

    def _battery_callback(self, key, msg):
        self._set_value(
            key,
            {
                "percentage": percent_from_battery(msg),
                "voltage": finite_float(msg.voltage),
                "current": finite_float(msg.current),
                "charge": finite_float(msg.charge),
                "capacity": finite_float(msg.capacity),
                "status": battery_status_label(msg.power_supply_status),
            },
        )

    def _cargo_current_id_callback(self, msg):
        cargo_id = str(msg.data).strip()
        self._set_value("cargo_current_id", cargo_id)
        if not cargo_id:
            return
        with self._lock:
            self._ensure_cargo_item(cargo_id)

    def _cargo_event_callback(self, msg):
        raw_event = str(msg.data)
        try:
            event_data = json.loads(raw_event)
            cargo_id = str(event_data.get("cargo_id") or "").strip()
            event = str(event_data.get("event") or raw_event).strip()
        except json.JSONDecodeError:
            cargo_id = ""
            event = raw_event.strip()

        received_label = time.strftime("%H:%M:%S")
        with self._lock:
            if not cargo_id:
                current = self._values.get("cargo_current_id")
                if current is not None:
                    cargo_id = str(current["value"]).strip()
            if not cargo_id:
                cargo_id = "unknown"

            item = self._ensure_cargo_item(cargo_id)
            item["latest_event"] = event
            item["state"] = self._cargo_state_from_event(event)
            item["updated_at"] = received_label
            item["event_count"] = int(item.get("event_count", 0)) + 1

            event_record = {
                "cargo_id": cargo_id,
                "event": event,
                "received_at": received_label,
                "raw": raw_event,
            }
            self._last_cargo_event = event_record
            self._cargo_events.append(event_record)
            self._cargo_events = self._cargo_events[-40:]

            self._values["cargo_last_event"] = {
                "value": event_record,
                "stamp": time.monotonic(),
            }

    def _ensure_cargo_item(self, cargo_id):
        item = self._cargo_items.get(cargo_id)
        if item is None:
            item = {
                "cargo_id": cargo_id,
                "state": "assigned",
                "latest_event": "assigned",
                "updated_at": time.strftime("%H:%M:%S"),
                "event_count": 0,
            }
            self._cargo_items[cargo_id] = item
        return item

    def _cargo_state_from_event(self, event):
        event_upper = str(event or "").upper()
        if any(key in event_upper for key in ("PICKED", "GRASPED")):
            return "picked"
        if any(key in event_upper for key in ("PLACED", "LOADED", "LOAD_DONE")):
            return "placed"
        if "CANCEL" in event_upper:
            return "cancelled"
        if "ASSIGN" in event_upper:
            return "assigned"
        return str(event or "updated")

    def _value(self, values, key):
        item = values.get(key)
        if item is None:
            return None
        return item["value"]

    def _age(self, values, key, now_monotonic):
        item = values.get(key)
        if item is None:
            return None
        return max(0.0, now_monotonic - item["stamp"])

    def _motion_summary(self, values, odom_key, cmd_key):
        odom = self._value(values, odom_key)
        cmd_vel = self._value(values, cmd_key)
        source = None
        speed = None
        linear_x = None
        angular_z = None

        if isinstance(odom, dict):
            source = "odom"
            speed = odom.get("speed_mps")
            linear_x = odom.get("linear_x")
            angular_z = odom.get("angular_z")
        if speed is None and isinstance(cmd_vel, dict):
            source = "cmd_vel"
            speed = cmd_vel.get("speed_mps")
            linear_x = cmd_vel.get("linear_x")
            angular_z = cmd_vel.get("angular_z")

        return {
            "speed_mps": speed,
            "linear_x_mps": linear_x,
            "angular_z_rad_s": angular_z,
            "source": source,
        }

    def _battery_ok(self, values, key):
        battery = self._value(values, key)
        if not isinstance(battery, dict):
            return None
        percentage = battery.get("percentage")
        if percentage is None:
            return None
        return float(percentage) >= 20.0

    def snapshot(self):
        now_monotonic = time.monotonic()
        with self._lock:
            values = dict(self._values)
            cargo_items = [dict(item) for item in self._cargo_items.values()]
            cargo_events = list(self._cargo_events)
            last_cargo_event = dict(self._last_cargo_event) if self._last_cargo_event else None

        target_spacing = self._float_param("target_spacing_m")
        heartbeat_timeout = self._float_param("heartbeat_timeout_s")
        follower_timeout = self._float_param("follower_timeout_s")
        heartbeat_age = self._age(values, "leader_heartbeat", now_monotonic)
        follower_status_age = self._age(values, "follower_status", now_monotonic)
        follower_safety_age = self._age(values, "follower_safety_state", now_monotonic)
        follower_age_candidates = [
            age for age in (follower_status_age, follower_safety_age) if age is not None
        ]
        follower_age = min(follower_age_candidates) if follower_age_candidates else None

        distance_error = self._value(values, "follower_distance_error_m")
        target_distance = self._value(values, "follower_target_distance_m")
        if distance_error is None and target_distance is not None:
            distance_error = target_distance - target_spacing

        leader_link = heartbeat_age is not None and heartbeat_age <= heartbeat_timeout
        follower_link = follower_age is not None and follower_age <= follower_timeout
        target_visible = self._value(values, "follower_target_visible")
        spacing_good = (
            distance_error is not None and abs(float(distance_error)) <= 0.05
        )
        safety_state = self._value(values, "follower_safety_state")
        safety_ok = safety_state in (None, "SAFE", "STOPPED")
        platoon_active = (
            self._value(values, "leader_follower_enable") is True and
            self._value(values, "leader_platoon_mode") == "FOLLOW"
        )
        task = classify_task(
            self._value(values, "mp_control_status"),
            self._value(values, "sim_pick_place_status"),
            self._value(values, "leader_task_state"),
            self._value(values, "leader_cargo_state"),
        )
        picked_count = sum(1 for item in cargo_items if item.get("state") in ("picked", "placed"))
        placed_count = sum(1 for item in cargo_items if item.get("state") == "placed")
        leader_motion = self._motion_summary(values, "leader_odom", "leader_cmd_vel")
        follower_motion = self._motion_summary(values, "follower_odom", "follower_cmd_vel")
        leader_battery_ok = self._battery_ok(values, "leader_battery")
        follower_battery_ok = self._battery_ok(values, "follower_battery")
        known_batteries = [
            item for item in (leader_battery_ok, follower_battery_ok) if item is not None
        ]
        battery_ok = all(known_batteries) if known_batteries else None

        if leader_link and follower_link and safety_ok:
            overall = "OK"
        elif leader_link or follower_link:
            overall = "WARN"
        else:
            overall = "WAIT"

        return {
            "server": {
                "time_unix": time.time(),
                "time_label": time.strftime("%Y-%m-%d %H:%M:%S"),
                "host_domain_id": os.environ.get("ROS_DOMAIN_ID", ""),
                "simulation_domain_id": int(self.get_parameter("simulation_domain_id").value),
                "follower_domain_id": int(self.get_parameter("follower_domain_id").value),
                "ros_domain_id": os.environ.get("ROS_DOMAIN_ID", ""),
                "target_spacing_m": target_spacing,
            },
            "leader": {
                "task_state": self._value(values, "leader_task_state"),
                "cargo_state": self._value(values, "leader_cargo_state"),
                "follower_enable": self._value(values, "leader_follower_enable"),
                "platoon_mode": self._value(values, "leader_platoon_mode"),
                "heartbeat_age_s": heartbeat_age,
                "cmd_vel": self._value(values, "leader_cmd_vel"),
                "odom": self._value(values, "leader_odom"),
                "motion": leader_motion,
                "battery": self._value(values, "leader_battery"),
                "battery_age_s": self._age(values, "leader_battery", now_monotonic),
            },
            "task": {
                **task,
                "mp_control_status": self._value(values, "mp_control_status"),
                "sim_pick_place_status": self._value(values, "sim_pick_place_status"),
            },
            "cargo": {
                "current_id": self._value(values, "cargo_current_id"),
                "picked_count": picked_count,
                "placed_count": placed_count,
                "items": list(reversed(cargo_items[-12:])),
                "events": list(reversed(cargo_events[-12:])),
                "last_event": last_cargo_event,
            },
            "follower": {
                "status": self._value(values, "follower_status"),
                "safety_state": safety_state,
                "cmd_vel": self._value(values, "follower_cmd_vel"),
                "odom": self._value(values, "follower_odom"),
                "motion": follower_motion,
                "battery": self._value(values, "follower_battery"),
                "battery_age_s": self._age(values, "follower_battery", now_monotonic),
                "distance_error_m": distance_error,
                "target_distance_m": target_distance,
                "target_visible": target_visible,
                "target_offset_x": self._value(values, "follower_target_offset_x"),
                "status_age_s": follower_status_age,
                "safety_age_s": follower_safety_age,
            },
            "health": {
                "overall": overall,
                "leader_link": leader_link,
                "follower_link": follower_link,
                "platoon_active": platoon_active,
                "target_visible": target_visible is True,
                "spacing_good": spacing_good,
                "safety_ok": safety_ok,
                "battery_ok": battery_ok,
                "leader_battery_ok": leader_battery_ok,
                "follower_battery_ok": follower_battery_ok,
            },
            "ages": {
                key: self._age(values, key, now_monotonic)
                for key in sorted(values.keys())
            },
            "video": {
                key: buffer.snapshot(now_monotonic)
                for key, buffer in self._video_buffers.items()
            },
        }

    def _start_http_server(self):
        host = self._str_param("host")
        port = int(self.get_parameter("port").value)
        web_root_param = self._str_param("web_root")
        if web_root_param:
            web_root = Path(web_root_param).expanduser().resolve()
        else:
            share_root = Path(
                get_package_share_directory("platooning_tablet_monitor")
            ).joinpath("web").resolve()
            source_root = Path(__file__).resolve().parents[1].joinpath("web").resolve()
            web_root = share_root if share_root.joinpath("index.html").is_file() else source_root

        handler = self._make_handler(web_root)
        self._server = ThreadingHTTPServer((host, port), handler)
        self._server_thread = Thread(
            target=self._server.serve_forever,
            daemon=True,
        )
        self._server_thread.start()
        self.get_logger().info(
            f"tablet monitor serving http://{host}:{port} from {web_root}"
        )

    def _make_handler(self, web_root):
        node = self

        class MonitorRequestHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path == "/api/status":
                    self._send_json(node.snapshot())
                    return
                if parsed.path == "/api/config":
                    self._send_json({
                        "target_spacing_m": node._float_param("target_spacing_m"),
                        "host_domain_id": os.environ.get("ROS_DOMAIN_ID", ""),
                        "simulation_domain_id": int(
                            node.get_parameter("simulation_domain_id").value
                        ),
                        "follower_domain_id": int(
                            node.get_parameter("follower_domain_id").value
                        ),
                        "ros_domain_id": os.environ.get("ROS_DOMAIN_ID", ""),
                    })
                    return
                if parsed.path.startswith("/frame/") and parsed.path.endswith(".jpg"):
                    key = parsed.path[len("/frame/"):-len(".jpg")]
                    self._send_video_frame(key)
                    return
                if parsed.path.startswith("/stream/"):
                    key = parsed.path[len("/stream/"):]
                    self._send_mjpeg_stream(key)
                    return
                self._send_static(parsed.path)

            def log_message(self, fmt, *args):
                node.get_logger().debug(fmt % args)

            def _send_json(self, payload):
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_video_frame(self, key):
                buffer = node._video_buffers.get(key)
                if buffer is None:
                    self.send_error(404)
                    return
                body, _, _, _ = buffer.latest()
                if body is None:
                    self.send_error(503)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_mjpeg_stream(self, key):
                buffer = node._video_buffers.get(key)
                if buffer is None:
                    self.send_error(404)
                    return

                self.send_response(200)
                self.send_header("Age", "0")
                self.send_header("Cache-Control", "no-cache, private")
                self.send_header("Pragma", "no-cache")
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()

                last_frame_count = -1
                while True:
                    frame, _, frame_count, _ = buffer.latest()
                    if frame is None or frame_count == last_frame_count:
                        buffer.wait(0.25)
                        frame, _, frame_count, _ = buffer.latest()
                    if frame is None:
                        continue
                    last_frame_count = frame_count
                    try:
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii"))
                        self.wfile.write(frame)
                        self.wfile.write(b"\r\n")
                    except (BrokenPipeError, ConnectionResetError):
                        return

            def _send_static(self, request_path):
                if request_path in ("", "/"):
                    relative = "index.html"
                else:
                    relative = unquote(request_path.lstrip("/"))
                requested = Path(relative)
                if requested.is_absolute() or ".." in requested.parts:
                    self.send_error(404)
                    return
                candidate = web_root.joinpath(requested).resolve()
                if not candidate.is_file():
                    self.send_error(404)
                    return

                content_type = mimetypes.guess_type(str(candidate))[0]
                if content_type is None:
                    content_type = "application/octet-stream"
                body = candidate.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return MonitorRequestHandler

    def destroy_node(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = PlatooningTabletMonitor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
