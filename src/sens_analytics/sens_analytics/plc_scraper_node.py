import rclpy
from rclpy.lifecycle import Node, Publisher, State, TransitionCallbackReturn
from std_msgs.msg import String


class PlcScraperNode(Node):
    def __init__(self):
        super().__init__('plc_scraper_node')
        self.pub_: Publisher = None
        self.timer_ = None
        self.last_checksum = "INITIAL_HASH"

        self.declare_parameter('poll_rate_hz', 0.1)

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('FSM Transition: Configuring PlcScraperNode...')
        self.pub_ = self.create_lifecycle_publisher(String, '/sens/raw_code_stream', 10)
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('FSM Transition: Activating PlcScraperNode (plc_polling mode)...')
        super().on_activate(state)

        # Получаем период поллинга
        hz = self.get_parameter('poll_rate_hz').get_parameter_value().double_value
        period = 1.0 / hz if hz > 0 else 10.0

        # Запускаем фоновый ROS Timer для опроса ПЛК
        self.timer_ = self.create_timer(period, self.timer_callback)
        self.get_logger().info(f'Started PLC polling timer every {period} seconds.')
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('FSM Transition: Deactivating PlcScraperNode... Going to sleep.')
        if self.timer_:
            self.timer_.cancel()
            self.destroy_timer(self.timer_)
            self.timer_ = None
        super().on_deactivate(state)
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('FSM Transition: Cleaning up PlcScraperNode...')
        if self.pub_:
            self.destroy_publisher(self.pub_)
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('FSM Transition: Shutting down PlcScraperNode...')
        if self.timer_:
            self.timer_.cancel()
            self.destroy_timer(self.timer_)
        return TransitionCallbackReturn.SUCCESS

    def check_plc_checksum(self):
        # Заглушка: Проверка чексуммы ПЛК через Snap7 / OPC UA
        # Для симуляции возвращаем новое значение при каждом 3 вызове (или просто новое)
        return "NEW_HASH_SIMULATED"

    def timer_callback(self):
        self.get_logger().debug('Polling PLC...')
        new_hash = self.check_plc_checksum()

        # Если хэш изменился - код на ПЛК был обновлен
        if new_hash != self.last_checksum:
            self.get_logger().info('PLC Checksum changed! Simulating SCL block download...')
            self.last_checksum = new_hash

            # Публикуем в топик
            if self.pub_ and self.pub_.is_activated:
                msg = String()
                msg.data = "SCL block delta content downloaded directly from PLC."
                self.pub_.publish(msg)
                self.get_logger().info('Published new SCL code from PLC.')

def main(args=None):
    rclpy.init(args=args)
    node = PlcScraperNode()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()
