import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import LifecycleNode, Node


def generate_launch_description():
    pkg_name = 'sens_analytics'

    # Путь до YAML конфигурации
    # Если пакет установлен корректно, get_package_share_directory вернет путь к config
    try:
        config_file = os.path.join(
            get_package_share_directory(pkg_name),
            'config',
            'source_params.yaml'
        )
    except Exception:
        # Fallback для тестирования, если пакет не скомпилирован через colcon
        config_file = os.path.join(
            os.path.dirname(__file__), '..', 'config', 'source_params.yaml'
        )

    # Определяем 4 Lifecycle ноды.
    # В ROS 2 Lifecycle-ноды по умолчанию стартуют в состоянии Unconfigured.

    file_watcher_node = LifecycleNode(
        package=pkg_name,
        executable='file_watcher_node',
        name='file_watcher_node',
        namespace='',
        output='screen',
        parameters=[config_file]
    )

    git_subscriber_node = LifecycleNode(
        package=pkg_name,
        executable='git_subscriber_node',
        name='git_subscriber_node',
        namespace='',
        output='screen',
        parameters=[config_file]
    )

    plc_scraper_node = LifecycleNode(
        package=pkg_name,
        executable='plc_scraper_node',
        name='plc_scraper_node',
        namespace='',
        output='screen',
        parameters=[config_file]
    )

    fallback_semantic_node = LifecycleNode(
        package=pkg_name,
        executable='fallback_semantic_node',
        name='fallback_semantic_node',
        namespace='',
        output='screen',
        parameters=[config_file]
    )

    # Основной менеджер Lifecycle (управляет состояниями остальных)
    lifecycle_manager_node = Node(
        package=pkg_name,
        executable='source_lifecycle_manager',
        name='source_lifecycle_manager',
        output='screen',
        parameters=[config_file]
    )

    # Мост: /sens/raw_code_stream  →  /sens/parse_code
    # Замыкает lifecycle-конвейер сбора данных с аналитическим ядром.
    code_bridge_node = Node(
        package=pkg_name,
        executable='code_bridge_node',
        name='code_bridge_node',
        output='screen',
        parameters=[config_file]
    )

    return LaunchDescription([
        file_watcher_node,
        git_subscriber_node,
        plc_scraper_node,
        fallback_semantic_node,
        lifecycle_manager_node,
        code_bridge_node
    ])
