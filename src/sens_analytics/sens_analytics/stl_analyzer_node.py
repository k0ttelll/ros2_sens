"""ROS 2 multi-threaded service node for static STL dependency analysis.

Exposes the ``/sens/parse_code`` service (``ParseStl``) which accepts raw
STL/AWL/SCL source text and returns a filtered JSON dependency graph.

The service callback runs inside a **``ReentrantCallbackGroup``** so that
CPU-bound parsing never blocks other callbacks (timers, lifecycle state-change
requests, ``call_async`` futures from ``code_bridge_node``).  The node is
intended to be spun with a ``MultiThreadedExecutor`` (4 threads by default).

A configurable ``max_input_chars`` guard rejects pathologically large inputs
before they reach the parser.
"""

from __future__ import annotations

import traceback

import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from sens_interfaces.srv import ParseStl

try:  # Prefer an external/copied stl_parser package when it is installed.
    from stl_parser import Parser
except ImportError:  # Fall back to the parser facade shipped in this ROS package.
    from .parser import Parser

from .graph_adapter import transform_pdg_to_sens_json

_EMPTY_GRAPH_JSON = '{"dependencies":[]}'
_DEFAULT_MAX_INPUT_CHARS = 500_000


class StlAnalyzerNode(Node):
    """Expose STL PDG analysis as a ROS 2 service (multi-threaded)."""

    def __init__(self) -> None:
        super().__init__("stl_analyzer_node")

        # --- Dedicated callback group so the service gets its own thread pool ---
        self._service_group = ReentrantCallbackGroup()

        # --- Configurable input-size guard ---
        self.declare_parameter(
            "max_input_chars", _DEFAULT_MAX_INPUT_CHARS
        )

        self._parser = Parser()
        self._service = self.create_service(
            ParseStl,
            "/sens/parse_code",
            self.parse_stl_callback,
            callback_group=self._service_group,
        )
        self.get_logger().info(
            "STL analyzer service is ready on /sens/parse_code (multi-threaded)"
        )

    def parse_stl_callback(
        self,
        request: ParseStl.Request,
        response: ParseStl.Response,
    ) -> ParseStl.Response:
        """Parse raw STL text and return the filtered Sens dependency JSON."""

        raw_stl = request.stl_code_text or ""
        self.get_logger().info(f"Received STL analysis request with {len(raw_stl)} characters")

        # --- Guard: reject oversized inputs early ---
        max_chars = self.get_parameter("max_input_chars").value
        if len(raw_stl) > max_chars:
            response.json_graph_output = _EMPTY_GRAPH_JSON
            response.success = False
            response.message = (
                f"Input too large: {len(raw_stl)} chars exceeds limit of {max_chars}"
            )
            self.get_logger().warn(response.message)
            return response

        try:
            pdg_graph = self._parse_to_pdg(raw_stl)
            response.json_graph_output = transform_pdg_to_sens_json(pdg_graph)
            response.success = True
            response.message = "OK"
            return response
        except Exception as exc:  # Keep parser/syntax failures inside the service boundary.
            response.json_graph_output = _EMPTY_GRAPH_JSON
            response.success = False
            response.message = f"{type(exc).__name__}: {exc}"
            self.get_logger().error(f"STL analysis failed: {response.message}")
            self.get_logger().error(traceback.format_exc())
            return response

    def _parse_to_pdg(self, raw_stl: str):
        if hasattr(self._parser, "parse_string_to_pdg"):
            return self._parser.parse_string_to_pdg(raw_stl)
        if hasattr(self._parser, "parse_to_pdg"):
            return self._parser.parse_to_pdg(raw_stl)
        if hasattr(self._parser, "parse"):
            return self._parser.parse(raw_stl)
        raise AttributeError("Parser does not expose a PDG parsing method")


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = StlAnalyzerNode()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
