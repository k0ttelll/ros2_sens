import rclpy
from rclpy.lifecycle import Node, Publisher, State, TransitionCallbackReturn
from std_msgs.msg import String


class FallbackSemanticNode(Node):
    def __init__(self):
        super().__init__('fallback_semantic_node')
        self.pub_: Publisher = None
        self.timer_ = None

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('FSM Transition: Configuring FallbackSemanticNode...')
        self.pub_ = self.create_lifecycle_publisher(String, '/sens/raw_code_stream', 10)
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('FSM Transition: Activating FallbackSemanticNode (know_how_fallback mode)...')
        super().on_activate(state)
        # Симулируем периодический сбор семантических тегов по OPC UA
        self.timer_ = self.create_timer(5.0, self.timer_callback)
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('FSM Transition: Deactivating FallbackSemanticNode... Going to sleep.')
        if self.timer_:
            self.timer_.cancel()
            self.destroy_timer(self.timer_)
            self.timer_ = None
        super().on_deactivate(state)
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('FSM Transition: Cleaning up FallbackSemanticNode...')
        if self.pub_:
            self.destroy_publisher(self.pub_)
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('FSM Transition: Shutting down FallbackSemanticNode...')
        if self.timer_:
            self.timer_.cancel()
            self.destroy_timer(self.timer_)
        return TransitionCallbackReturn.SUCCESS

    def timer_callback(self):
        # Отправляем метаданные вместо чистого исходного кода для семантического ИИ
        if self.pub_ and self.pub_.is_activated:
            msg = String()
            msg.data = '{"type": "metadata", "reason": "Know-How Protect activated on S7-1500", "tags": ["Motor1_Speed", "Sensor2_State"]}'
            self.pub_.publish(msg)
            self.get_logger().info('Published OPC UA fallback metadata for AI semantic analysis.')

def main(args=None):
    rclpy.init(args=args)
    node = FallbackSemanticNode()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()
