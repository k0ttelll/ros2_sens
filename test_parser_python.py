import rclpy
from sens_interfaces.srv import ParseStl
import json

def main():
    rclpy.init()
    node = rclpy.create_node('test_client')
    client = node.create_client(ParseStl, '/sens/parse_code')
    while not client.wait_for_service(timeout_sec=1.0):
        node.get_logger().info('service not available, waiting again...')
    
    req = ParseStl.Request()
    req.stl_code_text = "NETWORK 1\nL %I0.0\n= %Q0.0"
    future = client.call_async(req)
    rclpy.spin_until_future_complete(node, future)
    try:
        response = future.result()
        print(f"Success: {response.success}")
        print(f"Message: {response.message}")
        print(f"Graph Output: {json.dumps(json.loads(response.json_graph_output), indent=2)}")
    except Exception as e:
        print(f"Service call failed: {e}")
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
