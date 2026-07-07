# ros2_sens

`ros2_sens` is a ROS 2 workspace for an industrial PLC diagnostics pipeline. The project combines simulated PLC data acquisition, ROS 2 transport, storage-facing nodes, and static analysis of Siemens STL/AWL code.

The current focus is to turn raw PLC/STL program text into a clean engineering dependency graph that can be stored in a database and used by commissioning or maintenance tools.

## What Is Inside

```text
src/
  sens_interfaces/       Custom ROS 2 messages and services
  sens_drivers/          PLC simulator / driver-side nodes
  sens_storage/          Storage-facing receiver nodes
  sens_analytics/        STL static-analysis service and graph adapter
```

### Packages

`src/sens_interfaces`

Defines shared ROS 2 interfaces:

- `sens_interfaces/msg/RawLog` - raw PLC log/event message.
- `sens_interfaces/srv/ParseStl` - service for parsing STL text into a filtered dependency graph.

`src/sens_drivers`

Contains driver-side nodes. At the moment it includes:

- `sim_plc_node` - publishes simulated PLC raw log messages to `/sens/raw_logs`.

`src/sens_storage`

Contains storage-facing nodes. At the moment it includes:

- `storage_node` - subscribes to `/sens/raw_logs` and prints/handles incoming records.

`src/sens_analytics`

Contains static STL analysis logic:

- `parser.py`, `expression_parser.py`, `analysis/` - integrated parser core from `tetram1t/stl_parser`.
- `graph_adapter.py` - converts academic parser/PDG output into a clean industrial dependency JSON.
- `stl_analyzer_node.py` - ROS 2 service server for `/sens/parse_code`.
- `code_monitor_node.py` - **Lifecycle Node** that watches a directory for `.stl`/`.scl`/`.awl` changes via `watchdog`, debounces rapid IDE save events, and asynchronously calls `/sens/parse_code`.
- `source_lifecycle_manager.py` - ROS 2 node managing the dynamic state transitions of data collection nodes based on `source_mode`.
- Lifecycle nodes: `file_watcher_node.py`, `git_subscriber_node.py`, `plc_scraper_node.py`, `fallback_semantic_node.py`.

## Main ROS Interfaces

### Raw Logs

Topic:

```bash
/sens/raw_logs
```

Message:

```bash
ros2 interface show sens_interfaces/msg/RawLog
```

### STL Parsing Service

Service:

```bash
/sens/parse_code
```

Interface:

```bash
ros2 interface show sens_interfaces/srv/ParseStl
```

Request:

```text
string stl_code_text
```

Response:

```text
string json_graph_output
bool success
string message
```

The service returns JSON with this shape:

```json
{
  "dependencies": [
    {
      "source": "A1_Cyl3_Open_Sens",
      "target": "A1_Cyl3_Actuate",
      "block_name": "FC_Cylinder_Control",
      "network_number": 5,
      "type": "direct_logic"
    }
  ]
}
```

`type` is currently either:

- `direct_logic` - normal dependency, for example `A Sensor`.
- `inverted` - inverted dependency, for example `AN Sensor` or `ON Sensor`.

## Requirements

The repository is designed to run inside Docker with ROS 2 Humble.

The Docker image installs:

- ROS 2 Humble desktop base image
- `colcon`
- `rosdep`
- `git`
- `python3-networkx`
- `python3-pydot`
- `graphviz`
- `watchdog` (pip)

## Start The Docker Container

Build and start the container:

```bash
docker compose up -d --build
```

Enter the container:

```bash
docker exec -it ros2_humble_container bash
```

The workspace is mounted at:

```bash
/root/ros2_ws
```

## Build

Inside the container:

```bash
cd /root/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

To rebuild only the STL analysis service and interfaces:

```bash
cd /root/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select sens_interfaces sens_analytics --symlink-install
source install/setup.bash
```

## Run The Source Collection System

The `sens_analytics` package contains a modular architecture using ROS 2 Lifecycle Nodes to gather data from multiple sources (debug files, Git webhooks, PLC polling, OPC UA fallback) without restarting the main components.

To start the collection system and its Lifecycle Manager:

```bash
cd /root/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch sens_analytics source_system_launch.py
```

To dynamically switch the collection mode at runtime (for example, to `plc_polling`), publish to the manager's topic:

```bash
ros2 topic pub --once /sens/change_source_mode std_msgs/msg/String "{data: 'plc_polling'}"
```

## Run The Raw Log Demo

Open two terminals inside the container.

Terminal 1 - storage receiver:

```bash
cd /root/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 run sens_storage storage_node
```

Terminal 2 - PLC simulator:

```bash
cd /root/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 run sens_drivers sim_plc_node
```

Optional topic inspection:

```bash
ros2 topic echo /sens/raw_logs
```

Simulator parameters can be overridden at startup:

```bash
ros2 run sens_drivers sim_plc_node --ros-args \
  -p publish_period_ms:=50 \
  -p change_probability:=0.35
```

## Run The STL Analyzer Service

Terminal 1 - start the service server:

```bash
cd /root/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 run sens_analytics stl_analyzer_node
```

Expected log:

```text
STL analyzer service is ready on /sens/parse_code
```

Terminal 2 - call the service:

```bash
cd /root/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 service call /sens/parse_code sens_interfaces/srv/ParseStl "{stl_code_text: 'FUNCTION FC_Cylinder_Control
NETWORK 5
A A1_Cyl3_Open_Sens
AN A1_EStop_Active
= A1_Cyl3_Actuate
END_FUNCTION'}"
```

Expected response contains `success: true` and a JSON string similar to:

```json
{
  "dependencies": [
    {
      "source": "A1_Cyl3_Open_Sens",
      "target": "A1_Cyl3_Actuate",
      "block_name": "FC_Cylinder_Control",
      "network_number": 5,
      "type": "direct_logic"
    },
    {
      "source": "A1_EStop_Active",
      "target": "A1_Cyl3_Actuate",
      "block_name": "FC_Cylinder_Control",
      "network_number": 5,
      "type": "inverted"
    }
  ]
}
```

## Run The Code Monitor Node

The `code_monitor_node` is a Lifecycle Node that watches a local directory for `.stl`, `.scl`, and `.awl` file changes and automatically sends modified code to the `/sens/parse_code` service for analysis.

Terminal 1 — start the STL analysis service:

```bash
ros2 run sens_analytics stl_analyzer_node
```

Terminal 2 — start the code monitor node:

```bash
ros2 run sens_analytics code_monitor_node
```

Terminal 3 — activate the node through its lifecycle:

```bash
ros2 lifecycle set /code_monitor_node configure
ros2 lifecycle set /code_monitor_node activate
```

Now any `.stl`, `.scl`, or `.awl` file saved into the watched directory (default: `/root/ros2_ws/src/sens_analytics/test_code`) will be automatically parsed.

To override parameters at startup:

```bash
ros2 run sens_analytics code_monitor_node --ros-args \
  -p source_mode:=debug_file \
  -p watch_directory:=/path/to/code \
  -p debounce_seconds:=1.0
```

To deactivate monitoring:

```bash
ros2 lifecycle set /code_monitor_node deactivate
```

## How STL Graph Filtering Works

The analytics package uses the integrated `tetram1t/stl_parser` core to parse STL/AWL code and build intermediate analysis artifacts such as CFG/dataflow/reaching-definition structures.

`graph_adapter.py` then projects that academic representation into an industrial dependency model:

1. Tracks Siemens `NETWORK` boundaries.
2. Extracts block names such as `FUNCTION "FC_Cylinder_Control"`.
3. Treats real input logic instructions (`A`, `AN`, `O`, `ON`, `L`) as candidate sources.
4. Treats output/write instructions (`=`, `S`, `R`, `T`) as candidate targets.
5. Filters out internal or noisy operands such as accumulators, registers, jumps, constants, markers, DB internals, and temporary symbols.
6. Emits source-to-target dependencies enriched with block name, network number, and dependency type.

## Testing

The `sens_analytics` package includes a `pytest` test suite covering the core analysis modules. Tests are designed to run **without ROS 2** — only `networkx` and `pytest` are required.

### Running Tests

From the analytics package root:

```bash
cd src/sens_analytics
python3 -m pytest tests/ -v
```

Or from anywhere in the workspace:

```bash
python3 -m pytest src/sens_analytics/tests/ -v
```

### Test Coverage

| Module | Test File | Tests | What Is Covered |
|--------|-----------|-------|-----------------|
| `parser.py` | `tests/test_parser.py` | 22 | IR generation (`parse_stl_mvp`): instructions, labels, CFG edges, jumps, comments, warnings. PDG construction (`Parser`): direct/inverted deps, self-loops, network boundaries, transfer resets, block names |
| `graph_adapter.py` | `tests/test_graph_adapter.py` | 24 | Type mapping (direct_logic/inverted), noise filtering (accumulators, registers, markers, DB internals, temps, constants), deduplication, JSON contract, edge cases, **end-to-end** parser→adapter pipeline |
| `expression_parser.py` | `tests/test_expression_parser.py` | 12 | Single operands (A/AN/O/ON), nested blocks (A(/O(/)), empty input, tree serialization |

**Total: 59 tests** (as of v0.1.0).

### Dependencies

```bash
pip install pytest networkx
```

## Development Commands

Check package discovery:

```bash
ros2 pkg list | grep sens
```

Show interfaces:

```bash
ros2 interface show sens_interfaces/msg/RawLog
ros2 interface show sens_interfaces/srv/ParseStl
```

Run a focused build:

```bash
colcon build --packages-select sens_interfaces sens_analytics --symlink-install
```

Run Python syntax checks for the analytics package:

```bash
python3 -m compileall src/sens_analytics/sens_analytics
```

## Troubleshooting

### `Package not found`

Make sure the workspace overlay is sourced in the current shell:

```bash
source /opt/ros/humble/setup.bash
source /root/ros2_ws/install/setup.bash
```

### `ros2 service call` cannot find `/sens/parse_code`

Start the analyzer node first:

```bash
ros2 run sens_analytics stl_analyzer_node
```

Then check service discovery:

```bash
ros2 service list | grep sens
```

### GitHub SSH push fails with `Permission denied (publickey)`

The Docker container needs access to a GitHub SSH key. Either generate a key inside the container and add the public key to GitHub, or mount the host SSH directory into the container.

Generate a key inside the container:

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
cat ~/.ssh/id_ed25519.pub
```

Then add the printed public key in GitHub: Settings -> SSH and GPG keys -> New SSH key.

## CI/CD

The project uses **GitHub Actions** for continuous integration. The pipeline triggers on every push and pull request to `main` and `prerelease` branches.

### Pipeline Jobs

| Job | Runner | What It Does |
|-----|--------|-------------|
| 🔍 **Lint** | `ubuntu-latest` | Runs `ruff check` and `ruff format --check` on all Python code |
| 🧪 **Test** | `ubuntu-latest` | Runs 59 `pytest` tests (no ROS 2 needed) |
| 🔨 **Build** | `osrf/ros:humble-desktop` | Full `colcon build` + `colcon test` inside ROS 2 Humble container |

### Workflow File

```text
.github/workflows/ci.yml
```

### Concurrency

Previous runs on the same branch/PR are automatically cancelled to save CI minutes.

## Repository Hygiene

Generated ROS 2 folders should not be committed:

```text
build/
install/
log/
```

Source code and package metadata live under `src/` and should be committed.

## License

Project package metadata currently declares Apache-2.0. The integrated STL parser core was copied from `tetram1t/stl_parser`; keep its upstream license requirements in mind when distributing this repository.
