# Copyright 2026 ktj
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    simulation_bridge_config = os.path.join(
        get_package_share_directory("platooning_bridge_config"),
        "config",
        "leader_to_follower_bridge.yaml",
    )
    follower_bridge_config = os.path.join(
        get_package_share_directory("platooning_bridge_config"),
        "config",
        "follower_to_host_bridge.yaml",
    )

    return LaunchDescription(
        [
            Node(
                package="platooning_bridge_config",
                executable="leader_to_follower_domain_bridge.py",
                name="simulation_to_host_bridge",
                output="screen",
                arguments=[simulation_bridge_config],
            ),
            Node(
                package="platooning_bridge_config",
                executable="leader_to_follower_domain_bridge.py",
                name="follower_to_host_bridge",
                output="screen",
                arguments=[follower_bridge_config],
            ),
        ]
    )
