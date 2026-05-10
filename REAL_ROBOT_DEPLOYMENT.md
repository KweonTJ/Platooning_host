# 실로봇 배포 및 실행 가이드

이 문서는 현재 구성된 3개 워크스페이스를 실제 리더 로봇, 팔로워 로봇,
호스트 PC에 각각 넣고 플래투닝 시스템을 실행하는 절차를 정리한 문서이다.

## 워크스페이스 구성

| 역할 | 실행 장비 | 워크스페이스 | GitHub 저장소 |
| --- | --- | --- | --- |
| 리더 로봇 | TurtleBot3 Manipulation 로봇 | `~/turtlebot3_ws` | `https://github.com/KweonTJ/3D_pereception_Based_Mobile_Manipulator-Autonomous_Navigation_System.git` |
| 팔로워 로봇 | 플래투닝 팔로워 로봇 | `~/Turtlebot3_Platooning` | `https://github.com/KweonTJ/Turtlebot3_Platooning.git` |
| 호스트 PC | 브릿지 및 태블릿 모니터링 서버 | `~/platooning_host_ws` | `https://github.com/KweonTJ/Platooning_host.git` |

현재 로컬 기준 경로는 다음과 같다.

```text
리더 워크스페이스:   /home/ktj/turtlebot3_ws/src
팔로워 워크스페이스: /home/ktj/Desktop/Turtlebot3_Platooning/src
호스트 워크스페이스: /home/ktj/platooning_host_ws/src
```

## ROS 도메인 ID

현재 도메인 ID는 임시값이다. 추후 실제 네트워크 구성에 맞게 수정할 수 있지만,
한 번의 실행에서는 세 장비가 아래 기준을 동일하게 사용해야 한다.

| 도메인 | 현재 ID | 사용 대상 |
| --- | ---: | --- |
| 리더 로봇 도메인 | `10` | 리더 로봇, 리더 상태 토픽, 리더 명령 토픽 |
| 팔로워 로봇 도메인 | `20` | 팔로워 비전, 플래투닝 제어, 안전 제어, `/cmd_vel` |
| 호스트 모니터링 도메인 | `16` | 호스트 브릿지, 태블릿 웹 대시보드 |

모든 장비에서 ROS 실행 전에 아래 값을 설정한다.

```bash
export ROS_LOCALHOST_ONLY=0
```

## 네트워크 확인

1. 리더 로봇, 팔로워 로봇, 호스트 PC, 갤럭시 탭 S8을 같은 네트워크에 연결한다.
2. 각 장비에서 서로 `ping`이 되는지 확인한다.
3. 모든 장비에서 `ROS_LOCALHOST_ONLY=0`을 사용한다.
4. 호스트 PC 방화벽을 사용하는 경우 TCP `8080` 포트를 허용한다.
5. 태블릿에서는 호스트 PC의 LAN IP로 접속한다.

현재 호스트 PC에서 확인된 주소는 다음과 같았다.

```text
http://192.168.0.3:8080
```

네트워크가 바뀌면 호스트 PC에서 다시 확인한다.

```bash
hostname -I
```

`172.*` 주소는 Docker 쪽 주소일 가능성이 높으므로 태블릿 접속에는 보통
사용하지 않는다.

## 최초 설치

### 리더 로봇

리더 로봇에는 `turtlebot3_ws`를 만든다.

```bash
mkdir -p ~/turtlebot3_ws/src
cd ~/turtlebot3_ws/src
git clone https://github.com/KweonTJ/3D_pereception_Based_Mobile_Manipulator-Autonomous_Navigation_System.git .

cd ~/turtlebot3_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

### 팔로워 로봇

팔로워 로봇에는 `Turtlebot3_Platooning` 워크스페이스를 만든다.

```bash
mkdir -p ~/Turtlebot3_Platooning/src
cd ~/Turtlebot3_Platooning/src
git clone https://github.com/KweonTJ/Turtlebot3_Platooning.git .

cd ~/Turtlebot3_Platooning
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

### 호스트 PC

호스트 PC에는 `platooning_host_ws`를 만든다.

```bash
mkdir -p ~/platooning_host_ws/src
cd ~/platooning_host_ws/src
git clone https://github.com/KweonTJ/Platooning_host.git .

cd ~/platooning_host_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

## 실행 순서

실행 순서는 다음을 권장한다.

1. 호스트 PC 브릿지 및 태블릿 모니터 실행
2. 팔로워 로봇 실행
3. 리더 로봇 실행

호스트 브릿지와 팔로워 구독 노드가 먼저 떠 있어야 리더 작업 시작 시 상태 토픽을
놓칠 가능성이 줄어든다.

## 1. 호스트 PC 실행

호스트 PC는 리더 도메인 `10`과 팔로워 도메인 `20`의 토픽을 호스트 도메인
`16`으로 가져오고, 태블릿에서 볼 수 있는 웹 대시보드를 띄운다.

터미널 1에서 브릿지를 실행한다.

```bash
export ROS_LOCALHOST_ONLY=0
source /opt/ros/humble/setup.bash
source ~/platooning_host_ws/install/setup.bash
ros2 launch platooning_bridge_config bridge.launch.py
```

이 브릿지는 아래 두 경로를 동시에 연결한다.

```text
리더 도메인 10 -> 호스트 도메인 16
팔로워 도메인 20 -> 호스트 도메인 16
```

터미널 2에서 태블릿 모니터를 실행한다.

```bash
export ROS_DOMAIN_ID=16
export ROS_LOCALHOST_ONLY=0
source /opt/ros/humble/setup.bash
source ~/platooning_host_ws/install/setup.bash
ros2 launch platooning_tablet_monitor tablet_monitor.launch.py host:=0.0.0.0 port:=8080
```

브라우저 접속 주소는 다음과 같다.

```text
호스트 PC: http://localhost:8080
태블릿:    http://<host-pc-ip>:8080
```

갤럭시 탭 S8 기본 모델에서는 가로 모드로 보는 것을 기준으로 한다.

웹 상단에는 아래와 같이 표시되어야 한다.

```text
Host domain 16 · Simulation 10 · Follower 20
```

여기서 `Simulation 10`은 현재 리더 도메인으로 사용 중인 값이다. 실제 리더 로봇도
동일하게 도메인 `10`을 사용한다.

## 2. 팔로워 로봇 실행

팔로워 로봇은 도메인 `20`에서 실행한다. 팔로워는 리더 상태 토픽을 받아 플래투닝
상태를 판단하고, 카메라로 리더 마커를 추적한 뒤 안전 노드를 거쳐 최종 `/cmd_vel`을
발행한다.

```bash
export ROS_DOMAIN_ID=20
export ROS_LOCALHOST_ONLY=0
source /opt/ros/humble/setup.bash
source ~/Turtlebot3_Platooning/install/setup.bash
ros2 launch follower_bringup follower_system.launch.py start_rviz:=false
```

카메라 없이 노드 구동만 확인하려면 다음처럼 실행한다.

```bash
ros2 launch follower_bringup follower_system.launch.py use_camera:=false start_rviz:=false
```

카메라 장치 번호를 지정해야 할 경우:

```bash
ros2 launch follower_bringup follower_system.launch.py video_device:=/dev/video0 start_rviz:=false
```

팔로워 현재 설정은 다음과 같다.

- 리더 마커: ArUco
- 마커 ID: `0`
- 마커 사전: `DICT_4X4_50`
- 마커 크기: `0.10 m`
- 목표 거리: `0.45 m`
- `follower_platooning`은 `/follower/cmd_vel_raw`를 발행한다.
- 최종 `/cmd_vel`은 `follower_safety`만 발행한다.

## 3. 리더 로봇 실행

리더 로봇은 도메인 `10`에서 실행한다. 리더는 매니퓰레이터 하드웨어, 카메라,
CSRT/IBVS 인식, `mp_control`, 리더 상태 관리자, 비콘, 리더-팔로워 브릿지를 실행한다.

```bash
export ROS_DOMAIN_ID=10
export ROS_LOCALHOST_ONLY=0
source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash
ros2 launch mp_control real_pick_place.launch.py start_rviz:=false start_domain_bridge:=true
```

라이다를 같이 실행해야 할 경우:

```bash
export LDS_MODEL=LDS-01
ros2 launch mp_control real_pick_place.launch.py start_rviz:=false start_domain_bridge:=true start_lidar:=true
```

또는 LDS-02를 쓰는 경우:

```bash
export LDS_MODEL=LDS-02
ros2 launch mp_control real_pick_place.launch.py start_rviz:=false start_domain_bridge:=true start_lidar:=true
```

엔드이펙터 카메라 장치 번호를 지정해야 할 경우:

```bash
ros2 launch mp_control real_pick_place.launch.py start_rviz:=false start_domain_bridge:=true eef_camera_video_device:=/dev/video0
```

리더 실행 시 참고 사항:

- `real_pick_place.launch.py`는 실제 로봇용 pick-and-place 통합 런치이다.
- 실제 로봇 기본 인식은 depth-first 초기 검출 기준이다.
- 엔드이펙터 카메라는 근거리 보정용이며, 주 검출기는 전방 RGB-D 카메라이다.
- `start_domain_bridge:=true`는 리더 도메인 `10`의 `/leader/*` 토픽을 팔로워
  도메인 `20`으로 전달한다.
- 호스트 PC는 별도로 리더 도메인 `10`과 팔로워 도메인 `20`을 호스트 도메인
  `16`으로 가져온다.

## 실행 중 확인

### 호스트 PC 확인

```bash
export ROS_DOMAIN_ID=16
source /opt/ros/humble/setup.bash
source ~/platooning_host_ws/install/setup.bash
ros2 topic list | grep -E '/leader|/follower'
curl http://localhost:8080/api/status
```

정상 상태에서는 다음이 확인된다.

- `Leader Task`가 `-`에서 실제 리더 상태로 바뀐다.
- `Follower`가 `-`에서 팔로워 상태로 바뀐다.
- `/follower/distance_error`가 들어오면 `Live Spacing` 그래프가 움직인다.
- `Leader`, `Follower`, `Spacing`, `Safety` 상태 칸이 상황에 따라 초록색 또는
  노란색으로 바뀐다.

### 팔로워 로봇 확인

```bash
export ROS_DOMAIN_ID=20
source /opt/ros/humble/setup.bash
source ~/Turtlebot3_Platooning/install/setup.bash
ros2 topic echo /leader/heartbeat --once
ros2 topic echo /follower/status --once
ros2 topic echo /cmd_vel --once
```

### 리더 로봇 확인

```bash
export ROS_DOMAIN_ID=10
source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash
ros2 topic echo /leader/heartbeat --once
ros2 topic echo /leader/task_state --once
ros2 topic echo /mp_control/status --once
```

## 종료 방법

각 터미널에서 실행 중인 launch는 `Ctrl+C`로 종료한다.

호스트에서 `systemd-run`으로 임시 서비스를 띄운 경우에는 다음 명령으로 종료한다.

```bash
systemctl --user stop platooning_tablet_monitor.service
systemctl --user stop platooning_host_bridge.service
```

## 문제 해결

### 태블릿 페이지는 열리지만 값이 전부 `-` 또는 `WAIT`인 경우

웹 서버는 실행 중이지만 ROS 토픽이 호스트 도메인 `16`으로 들어오지 않는 상태이다.

호스트 브릿지 상태를 확인한다.

```bash
systemctl --user status platooning_host_bridge.service --no-pager -l
```

또는 브릿지를 직접 실행한다.

```bash
export ROS_LOCALHOST_ONLY=0
source /opt/ros/humble/setup.bash
source ~/platooning_host_ws/install/setup.bash
ros2 launch platooning_bridge_config bridge.launch.py
```

### 태블릿에서 페이지가 열리지 않는 경우

호스트 PC에서 웹 서버와 포트를 확인한다.

```bash
ss -ltnp | grep ':8080'
curl http://localhost:8080
```

태블릿에서는 아래 형식으로 접속한다.

```text
http://<host-pc-ip>:8080
```

### 팔로워가 움직이지 않는 경우

팔로워 도메인 `20`에서 아래 토픽을 확인한다.

```bash
ros2 topic echo /leader/follower_enable --once
ros2 topic echo /leader/platoon_mode --once
ros2 topic echo /follower/target_visible --once
ros2 topic echo /follower/cmd_vel_raw --once
ros2 topic echo /cmd_vel --once
```

`/follower/cmd_vel_raw`는 변하지만 `/cmd_vel`이 변하지 않으면 `follower_safety`
쪽에서 정지시키고 있는지 확인한다.

### 팔로워에는 리더 데이터가 보이는데 호스트 홈페이지에는 안 보이는 경우

리더-팔로워 브릿지는 정상일 수 있지만, 호스트 브릿지가 꺼져 있을 수 있다.
호스트 PC에서 아래를 확인한다.

```bash
export ROS_DOMAIN_ID=16
source /opt/ros/humble/setup.bash
source ~/platooning_host_ws/install/setup.bash
ros2 topic echo /leader/task_state --once
```

값이 나오지 않으면 호스트 브릿지를 다시 실행한다.

```bash
export ROS_LOCALHOST_ONLY=0
source /opt/ros/humble/setup.bash
source ~/platooning_host_ws/install/setup.bash
ros2 launch platooning_bridge_config bridge.launch.py
```
