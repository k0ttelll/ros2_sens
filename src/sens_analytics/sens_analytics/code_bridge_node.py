"""Bridge node: route STL code from /sens/raw_code_stream to /sens/parse_code.

Closes the gap in the lifecycle collection pipeline: the four lifecycle source
nodes (``file_watcher_node``, ``git_subscriber_node``, ``plc_scraper_node``,
``fallback_semantic_node``) publish raw STL/SCL text to ``/sens/raw_code_stream``
as ``std_msgs/String``. This node subscribes to that topic and forwards each
non-empty payload as a ``ParseStl`` service request to ``/sens/parse_code``.

Messages are dropped with a warning when the analyzer service is unavailable, so
a missing/analyzer never blocks the collection nodes.
"""

from __future__ import annotations

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sens_interfaces.srv import ParseStl


class CodeBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("code_bridge_node")

        self._parse_client = self.create_client(ParseStl, "/sens/parse_code")
        self._sub = self.create_subscription(
            String,
            "/sens/raw_code_stream",
            self._on_raw_code,
            10,
        )

        self.get_logger().info(
            "CodeBridgeNode ready — /sens/raw_code_stream  →  /sens/parse_code"
        )

    def _on_raw_code(self, msg: String) -> None:
        code_text = msg.data
        if not code_text or not code_text.strip():
            return

        if not self._parse_client.service_is_ready():
            self.get_logger().warn(
                f"/sens/parse_code unavailable — dropping message ({len(code_text)} chars)"
            )
            return

        request = ParseStl.Request()
        request.stl_code_text = code_text
        self.get_logger().info(
            f"Forwarding {len(code_text)} chars  →  /sens/parse_code"
        )
        future = self._parse_client.call_async(request)
        future.add_done_callback(self._on_parse_result)

    def _on_parse_result(self, future) -> None:
        try:
            response: ParseStl.Response = future.result()
        except Exception as exc:
            self.get_logger().error(f"Service call failed: {exc}")
            return

        if response.success:
            self.get_logger().info(
                f"[✓] Parsed OK — json_len={len(response.json_graph_output)}"
            )
        else:
            self.get_logger().warn(f"[✗] Parse error: {response.message}")


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = CodeBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
