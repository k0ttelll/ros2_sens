import rclpy
from lifecycle_msgs.msg import Transition
from lifecycle_msgs.srv import ChangeState
from rclpy.node import Node
from std_msgs.msg import String


class SourceLifecycleManager(Node):
    def __init__(self):
        super().__init__('source_lifecycle_manager')

        self.declare_parameter('source_mode', 'debug_file')
        self.current_mode = self.get_parameter('source_mode').get_parameter_value().string_value

        self.get_logger().info(f'Starting with source_mode: {self.current_mode}')

        # Маппинг режимов на имена нод
        self.mode_to_node = {
            'debug_file': 'file_watcher_node',
            'git_webhook': 'git_subscriber_node',
            'plc_polling': 'plc_scraper_node',
            'know_how_fallback': 'fallback_semantic_node'
        }

        self.all_nodes = list(self.mode_to_node.values())

        # Создаем клиенты для управления жизненным циклом каждой ноды
        self.lifecycle_clients = {}
        for node_name in self.all_nodes:
            change_srv_name = f'/{node_name}/change_state'
            self.lifecycle_clients[node_name] = self.create_client(ChangeState, change_srv_name)

        # Таймер для инициализации (даем нодам время запуститься)
        self.timer = self.create_timer(2.0, self.startup_nodes)

        # ROS 2 Service для смены режима (здесь реализован через Topic для простоты передачи строк без кастомных .srv)
        # В полноценном варианте можно использовать Service Server с кастомным типом.
        self.mode_sub = self.create_subscription(
            String,
            '/sens/change_source_mode',
            self.change_mode_callback,
            10
        )
        self.get_logger().info('Lifecycle Manager is ready. Waiting for node registration...')

    def startup_nodes(self):
        self.timer.cancel()
        self.get_logger().info("Initializing all managed nodes to CONFIGURED state...")

        # Переводим все ноды в состояние Unconfigured -> Configured
        for node_name in self.all_nodes:
            self.change_node_state(node_name, Transition.TRANSITION_CONFIGURE)

        # Активируем стартовый режим
        self.activate_mode(self.current_mode)

    def change_mode_callback(self, msg: String):
        new_mode = msg.data
        if new_mode not in self.mode_to_node:
            self.get_logger().error(f"Unknown mode requested: {new_mode}")
            return

        if new_mode == self.current_mode:
            self.get_logger().info(f"System is already in mode: {new_mode}")
            return

        self.get_logger().info(f"--- FSM Transition: Switching mode from {self.current_mode} to {new_mode} ---")

        # Усыпляем текущую ноду (Active -> Inactive)
        old_node = self.mode_to_node[self.current_mode]
        self.change_node_state(old_node, Transition.TRANSITION_DEACTIVATE)

        # Пробуждаем новую ноду (Inactive -> Active)
        self.current_mode = new_mode
        self.activate_mode(self.current_mode)

    def activate_mode(self, mode):
        node_name = self.mode_to_node[mode]
        self.get_logger().info(f"FSM Transition: Activating node for mode '{mode}' -> {node_name}")
        self.change_node_state(node_name, Transition.TRANSITION_ACTIVATE)

    def change_node_state(self, node_name, transition_id):
        client = self.lifecycle_clients[node_name]
        if not client.wait_for_service(timeout_sec=2.0):
            self.get_logger().warn(f"Lifecycle Service {client.srv_name} not available. Node might not be running.")
            return False

        req = ChangeState.Request()
        req.transition.id = transition_id

        future = client.call_async(req)
        future.add_done_callback(lambda f: self.transition_result_cb(f, node_name, transition_id))
        return True

    def transition_result_cb(self, future, node_name, transition_id):
        try:
            res = future.result()
            if res.success:
                self.get_logger().info(f"FSM Success: Node '{node_name}' successfully transitioned (id: {transition_id}).")
            else:
                self.get_logger().error(f"FSM Error: Node '{node_name}' failed to transition (id: {transition_id}).")
        except Exception as e:
            self.get_logger().error(f"Exception calling service for '{node_name}': {e}")

def main(args=None):
    rclpy.init(args=args)
    manager = SourceLifecycleManager()
    rclpy.spin(manager)
    manager.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
