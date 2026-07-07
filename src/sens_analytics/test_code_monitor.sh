#!/bin/bash
set -e

source /opt/ros/humble/setup.bash
source /root/ros2_ws/install/setup.bash

echo "=== [1/6] Creating test directory ==="
mkdir -p /root/ros2_ws/src/sens_analytics/test_code

echo "=== [2/6] Starting stl_analyzer_node (service server) ==="
ros2 run sens_analytics stl_analyzer_node &
ANALYZER_PID=$!
sleep 2

echo "=== [3/6] Starting code_monitor_node ==="
ros2 run sens_analytics code_monitor_node &
MONITOR_PID=$!
sleep 1

echo "=== [4/6] Lifecycle: configure → activate ==="
ros2 lifecycle set /code_monitor_node configure
sleep 1
ros2 lifecycle set /code_monitor_node activate
sleep 1

echo "=== [5/6] Writing test .stl file to trigger watchdog ==="
cat > /root/ros2_ws/src/sens_analytics/test_code/test_block.stl << 'STLEOF'
FUNCTION_BLOCK FB_TestMotor
VAR_INPUT
    Start : BOOL;
    Speed : INT;
END_VAR
VAR_OUTPUT
    Running : BOOL;
END_VAR
BEGIN
    IF Start THEN
        Running := TRUE;
    END_IF;
END_FUNCTION_BLOCK
STLEOF

echo "=== Waiting for debounce (3s)... ==="
sleep 3

echo "=== [6/6] Cleanup: deactivate → shutdown ==="
ros2 lifecycle set /code_monitor_node deactivate 2>/dev/null || true
sleep 1
kill $MONITOR_PID $ANALYZER_PID 2>/dev/null || true
wait $MONITOR_PID $ANALYZER_PID 2>/dev/null || true
echo "=== ✓ Integration test complete ==="
