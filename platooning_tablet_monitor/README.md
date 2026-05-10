# Platooning Tablet Monitor

Tablet-friendly web monitor for the platooning host PC.

## Run

Use the ROS domain that can see the bridged leader topics and follower topics.

```bash
export ROS_DOMAIN_ID=16
export ROS_LOCALHOST_ONLY=0

source /opt/ros/humble/setup.bash
source ~/platooning_host_ws/install/setup.bash

ros2 launch platooning_tablet_monitor tablet_monitor.launch.py host:=0.0.0.0 port:=8080
```

Open this from the tablet on the same network:

```text
http://<host-pc-ip>:8080
```

## Topics

- `/leader/task_state`
- `/leader/cargo_state`
- `/leader/follower_enable`
- `/leader/platoon_mode`
- `/leader/heartbeat`
- `/leader/cmd_vel`
- `/leader/odom`
- `/follower/status`
- `/follower/safety_state`
- `/follower/distance_error`
- `/follower/target_visible`
- `/follower/target_distance`
- `/follower/target_offset_x`
