#!/bin/bash
cd /root/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 service call /sens/parse_code sens_interfaces/srv/ParseStl "{stl_code_text: 'NETWORK 1
L %I0.0
= %Q0.0'}"
