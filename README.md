# Platooning Host

Host-side ROS 2 workspace packages for platooning bridge and tablet monitoring.

## Packages

- `platooning_bridge_config`: bridges leader topics from the leader domain to the follower domain.
- `platooning_tablet_monitor`: serves a tablet-friendly web dashboard for leader/follower state.

## Build

```bash
cd ~/platooning_host_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

## Run Bridge

The current domain IDs are temporary.

```bash
export ROS_LOCALHOST_ONLY=0
source /opt/ros/humble/setup.bash
source ~/platooning_host_ws/install/setup.bash
ros2 launch platooning_bridge_config bridge.launch.py
```

## Run Tablet Monitor

Run this in the domain that can see the bridged leader topics and follower topics.
With the current temporary setup, use the follower domain.

```bash
export ROS_DOMAIN_ID=20
export ROS_LOCALHOST_ONLY=0
source /opt/ros/humble/setup.bash
source ~/platooning_host_ws/install/setup.bash
ros2 launch platooning_tablet_monitor tablet_monitor.launch.py host:=0.0.0.0 port:=8080
```

Open from a tablet on the same network:

```text
http://<host-pc-ip>:8080
```
