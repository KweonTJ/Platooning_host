# Platooning Host

플래투닝 브릿지와 태블릿 모니터링 웹 서버를 실행하는 호스트 PC용 ROS 2
워크스페이스 패키지 모음

실제 리더 로봇, 팔로워 로봇, 호스트 PC를 나누어 실행하는 전체 절차는
[`REAL_ROBOT_DEPLOYMENT.md`](REAL_ROBOT_DEPLOYMENT.md)를 참고

## 패키지 구성

- `platooning_bridge_config`: 리더 도메인과 팔로워 도메인의 상태 토픽을 호스트
  모니터링 도메인으로 가져오는 브릿지 패키지
- `platooning_tablet_monitor`: 갤럭시 탭 S8 또는 호스트 PC 브라우저에서 확인할 수
  있는 웹 기반 플래투닝 대시보드

## 빌드

```bash
cd ~/platooning_host_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

## 현재 도메인 ID

현재 도메인 ID는 현재 실제 로봇 SSH 설정 기준값입니다.

- 리더 로봇 도메인: `25`
- 팔로워 로봇 도메인: `73`
- 호스트 PC / 태블릿 모니터 도메인: `16`

## 브릿지 실행

호스트 PC에서 실행합니다. 리더 도메인 `25`와 팔로워 도메인 `73`의 토픽을
호스트 도메인 `16`으로 가져옵니다.

```bash
export ROS_LOCALHOST_ONLY=0
source /opt/ros/humble/setup.bash
source ~/platooning_host_ws/install/setup.bash
ros2 launch platooning_bridge_config bridge.launch.py
```

## 태블릿 모니터 실행

호스트 PC 도메인에서 실행합니다. 현재 호스트 PC/태블릿 모니터 도메인은 `ROS_DOMAIN_ID=16`을 사용합니다.

```bash
export ROS_DOMAIN_ID=16
export ROS_LOCALHOST_ONLY=0
source /opt/ros/humble/setup.bash
source ~/platooning_host_ws/install/setup.bash
ros2 launch platooning_tablet_monitor tablet_monitor.launch.py host:=0.0.0.0 port:=8080
```

같은 네트워크에 연결된 태블릿에서 아래 주소로 접속합니다.

```text
http://<host-pc-ip>:8080
```

호스트 PC에서 직접 확인할 때는 아래 주소를 사용할 수 있습니다.

```text
http://localhost:8080
```

## 추가 문서

- [라즈베리파이 모니터링 서버 전달 자료](docs/raspberry_pi_server_handoff.pdf)
- [라즈베리파이 모니터링 서버 전달 자료 HTML 원본](docs/raspberry_pi_server_handoff.html)
