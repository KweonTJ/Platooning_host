# Real Robot Deployment Runbook

This document describes how to deploy and run the current three-workspace
platooning system on the real leader robot, follower robot, and host PC.

## Workspaces

| Role | Machine | Workspace | Repository |
| --- | --- | --- | --- |
| Leader robot | TurtleBot3 Manipulation robot | `~/turtlebot3_ws` | `https://github.com/KweonTJ/3D_pereception_Based_Mobile_Manipulator-Autonomous_Navigation_System.git` |
| Follower robot | Platooning follower robot | `~/Turtlebot3_Platooning` | `https://github.com/KweonTJ/Turtlebot3_Platooning.git` |
| Host PC | Monitoring and tablet web server | `~/platooning_host_ws` | `https://github.com/KweonTJ/Platooning_host.git` |

## Domain IDs

These IDs are temporary and can be changed later, but all three machines must
use the same convention during one run.

| Domain | Current ID | Used by |
| --- | ---: | --- |
| Leader / simulation domain | `10` | Leader robot and leader-side state topics |
| Follower robot domain | `20` | Follower vision, platooning, safety, and `/cmd_vel` |
| Host monitor domain | `16` | Host bridge and tablet monitor |

Set this on every machine before running ROS:

```bash
export ROS_LOCALHOST_ONLY=0
```

## Network Checklist

1. Put the leader robot, follower robot, host PC, and Galaxy Tab S8 on the same
   network.
2. Confirm each machine can ping the host PC and the robot PCs.
3. Keep `ROS_LOCALHOST_ONLY=0` on all three machines.
4. Allow TCP port `8080` on the host PC if a firewall is enabled.
5. Use the host PC LAN IP for the tablet. On the current host PC it was:

```text
http://192.168.0.3:8080
```

Re-check the IP when the network changes:

```bash
hostname -I
```

## First-Time Setup

### Leader Robot

```bash
mkdir -p ~/turtlebot3_ws/src
cd ~/turtlebot3_ws/src
git clone https://github.com/KweonTJ/3D_pereception_Based_Mobile_Manipulator-Autonomous_Navigation_System.git .

cd ~/turtlebot3_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

### Follower Robot

```bash
mkdir -p ~/Turtlebot3_Platooning/src
cd ~/Turtlebot3_Platooning/src
git clone https://github.com/KweonTJ/Turtlebot3_Platooning.git .

cd ~/Turtlebot3_Platooning
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

### Host PC

```bash
mkdir -p ~/platooning_host_ws/src
cd ~/platooning_host_ws/src
git clone https://github.com/KweonTJ/Platooning_host.git .

cd ~/platooning_host_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

## Run Order

Start the system in this order so subscribers and bridges are ready before the
task starts.

## 1. Host PC

The host PC bridges leader domain `10` and follower domain `20` into host domain
`16`, then serves the tablet dashboard.

Terminal 1:

```bash
export ROS_LOCALHOST_ONLY=0
source /opt/ros/humble/setup.bash
source ~/platooning_host_ws/install/setup.bash
ros2 launch platooning_bridge_config bridge.launch.py
```

Terminal 2:

```bash
export ROS_DOMAIN_ID=16
export ROS_LOCALHOST_ONLY=0
source /opt/ros/humble/setup.bash
source ~/platooning_host_ws/install/setup.bash
ros2 launch platooning_tablet_monitor tablet_monitor.launch.py host:=0.0.0.0 port:=8080
```

Open the dashboard:

```text
Host PC: http://localhost:8080
Tablet:  http://<host-pc-ip>:8080
```

The top line should show:

```text
Host domain 16 · Simulation 10 · Follower 20
```

## 2. Follower Robot

The follower runs in domain `20`. It reads leader state bridged from domain `10`,
tracks the leader marker, applies platooning control, and publishes final
`/cmd_vel` through `follower_safety`.

```bash
export ROS_DOMAIN_ID=20
export ROS_LOCALHOST_ONLY=0
source /opt/ros/humble/setup.bash
source ~/Turtlebot3_Platooning/install/setup.bash
ros2 launch follower_bringup follower_system.launch.py start_rviz:=false
```

Useful options:

```bash
ros2 launch follower_bringup follower_system.launch.py use_camera:=false start_rviz:=false
ros2 launch follower_bringup follower_system.launch.py video_device:=/dev/video0 start_rviz:=false
```

Follower assumptions:

- The leader has the configured ArUco marker visible to the follower camera.
- Current marker config is ID `0`, dictionary `DICT_4X4_50`, size `0.10 m`.
- Current target distance is `0.45 m`.
- `follower_platooning` publishes `/follower/cmd_vel_raw`.
- Only `follower_safety` publishes final `/cmd_vel`.

## 3. Leader Robot

The leader runs in domain `10`. It starts the manipulation hardware, camera,
CSRT/IBVS perception, `mp_control`, leader task manager, beacon, and the optional
leader-to-follower bridge.

```bash
export ROS_DOMAIN_ID=10
export ROS_LOCALHOST_ONLY=0
source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash
ros2 launch mp_control real_pick_place.launch.py start_rviz:=false start_domain_bridge:=true
```

Useful options:

```bash
ros2 launch mp_control real_pick_place.launch.py start_rviz:=false start_domain_bridge:=true start_lidar:=true
ros2 launch mp_control real_pick_place.launch.py start_rviz:=false start_domain_bridge:=true eef_camera_video_device:=/dev/video0
```

If `start_lidar:=true`, set the lidar model first:

```bash
export LDS_MODEL=LDS-01
```

or:

```bash
export LDS_MODEL=LDS-02
```

Leader notes:

- `real_pick_place.launch.py` defaults to depth-first object initialization.
- The end-effector camera is near-field refinement, not the primary detector.
- `start_domain_bridge:=true` bridges `/leader/*` topics from domain `10` to
  follower domain `20`.
- The host PC separately mirrors leader domain `10` and follower domain `20`
  into monitor domain `16`.

## Runtime Checks

### Host PC

```bash
export ROS_DOMAIN_ID=16
source /opt/ros/humble/setup.bash
source ~/platooning_host_ws/install/setup.bash
ros2 topic list | grep -E '/leader|/follower'
curl http://localhost:8080/api/status
```

Expected dashboard behavior:

- `Leader Task` changes from `-` after leader state starts arriving.
- `Follower` changes from `-` after follower status starts arriving.
- `Live Spacing` updates after `/follower/distance_error` is received.
- `Leader`, `Follower`, `Spacing`, and `Safety` cells turn green or yellow
  depending on current state.

### Follower Robot

```bash
export ROS_DOMAIN_ID=20
source /opt/ros/humble/setup.bash
source ~/Turtlebot3_Platooning/install/setup.bash
ros2 topic echo /leader/heartbeat --once
ros2 topic echo /follower/status --once
ros2 topic echo /cmd_vel --once
```

### Leader Robot

```bash
export ROS_DOMAIN_ID=10
source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash
ros2 topic echo /leader/heartbeat --once
ros2 topic echo /leader/task_state --once
ros2 topic echo /mp_control/status --once
```

## Shutdown

Stop the launch processes with `Ctrl+C` in each terminal.

If the host services were started through `systemd-run`, stop them with:

```bash
systemctl --user stop platooning_tablet_monitor.service
systemctl --user stop platooning_host_bridge.service
```

## Troubleshooting

### The tablet page opens but all values are `-` or `WAIT`

The web server is running, but ROS data is not reaching domain `16`.

Check host bridge:

```bash
systemctl --user status platooning_host_bridge.service --no-pager -l
```

Or run it manually:

```bash
export ROS_LOCALHOST_ONLY=0
source /opt/ros/humble/setup.bash
source ~/platooning_host_ws/install/setup.bash
ros2 launch platooning_bridge_config bridge.launch.py
```

### The tablet cannot open the page

Check the host server and port:

```bash
ss -ltnp | grep ':8080'
curl http://localhost:8080
```

Then open this on the tablet:

```text
http://<host-pc-ip>:8080
```

### Follower does not move

Check these in domain `20`:

```bash
ros2 topic echo /leader/follower_enable --once
ros2 topic echo /leader/platoon_mode --once
ros2 topic echo /follower/target_visible --once
ros2 topic echo /follower/cmd_vel_raw --once
ros2 topic echo /cmd_vel --once
```

If `/follower/cmd_vel_raw` changes but `/cmd_vel` does not, inspect
`follower_safety`.

### Leader data appears on follower but not on host

The leader-to-follower bridge may be working, but the host bridge may not be.
Run this on the host PC:

```bash
export ROS_DOMAIN_ID=16
source /opt/ros/humble/setup.bash
source ~/platooning_host_ws/install/setup.bash
ros2 topic echo /leader/task_state --once
```
