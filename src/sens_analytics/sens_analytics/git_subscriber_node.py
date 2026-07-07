import rclpy
from rclpy.lifecycle import Node, Publisher, State, TransitionCallbackReturn
from std_msgs.msg import String


class GitSubscriberNode(Node):
    def __init__(self):
        super().__init__('git_subscriber_node')
        self.pub_: Publisher = None

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('FSM Transition: Configuring GitSubscriberNode...')
        self.pub_ = self.create_lifecycle_publisher(String, '/sens/raw_code_stream', 10)
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('FSM Transition: Activating GitSubscriberNode (git_webhook mode)...')
        super().on_activate(state)
        # Заглушка: Здесь можно поднять Flask/FastAPI сервер для приема вебхуков от GitLab
        self.get_logger().info('Webhook listener initialized. Ready to receive TIA Portal VCI events.')
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('FSM Transition: Deactivating GitSubscriberNode... Going to sleep.')
        # Заглушка: Остановка сервера вебхуков
        super().on_deactivate(state)
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('FSM Transition: Cleaning up GitSubscriberNode...')
        if self.pub_:
            self.destroy_publisher(self.pub_)
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('FSM Transition: Shutting down GitSubscriberNode...')
        return TransitionCallbackReturn.SUCCESS

    def webhook_callback(self, payload):
        # Метод-заглушка, вызываемый при получении HTTP POST запроса (вебхука)
        if self.pub_ and self.pub_.is_activated:
            msg = String()
            msg.data = f"Simulated code from Git VCI: {payload}"
            self.pub_.publish(msg)
            self.get_logger().info('Published Git webhook data.')

def main(args=None):
    rclpy.init(args=args)
    node = GitSubscriberNode()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()
