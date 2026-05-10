import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    package_share = get_package_share_directory("platooning_tablet_monitor")
    default_params = os.path.join(package_share, "config", "tablet_monitor_params.yaml")

    host = LaunchConfiguration("host")
    port = LaunchConfiguration("port")
    params_file = LaunchConfiguration("params_file")

    return LaunchDescription([
        DeclareLaunchArgument("host", default_value="0.0.0.0"),
        DeclareLaunchArgument("port", default_value="8080"),
        DeclareLaunchArgument("params_file", default_value=default_params),
        Node(
            package="platooning_tablet_monitor",
            executable="tablet_monitor_server",
            name="platooning_tablet_monitor",
            output="screen",
            parameters=[
                params_file,
                {
                    "host": host,
                    "port": ParameterValue(port, value_type=int),
                },
            ],
        ),
    ])
