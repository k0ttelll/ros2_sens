"""Real-time code-change monitor — ROS 2 Managed (Lifecycle) Node.

Watches a local directory for .stl / .scl / .awl file modifications via the
``watchdog`` library.  Rapid filesystem events produced by IDE auto-save are
coalesced with a debounce timer so that the ``/sens/parse_code`` service is
called only once after the file has stabilised.

Lifecycle contract
------------------
* **on_configure** — declares parameters, creates the service client.
* **on_activate**  — starts the ``watchdog.Observer`` thread.
* **on_deactivate** — stops the observer and cancels pending debounce timers
  (prevents thread leaks across mode switches).
* **on_cleanup / on_shutdown** — defensive teardown.

Integration
-----------
Register in ``setup.py``::

    "code_monitor_node = sens_analytics.code_monitor_node:main"

Add parameters to ``source_params.yaml``::

    /code_monitor_node:
      ros__parameters:
        source_mode: "debug_file"
        watch_directory: "/root/ros2_ws/src/sens_analytics/test_code"
        debounce_seconds: 0.7
"""

from __future__ import annotations

import os
import threading

import rclpy
from rclpy.lifecycle import Node as LifecycleNode
from rclpy.lifecycle import State, TransitionCallbackReturn
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from sens_interfaces.srv import ParseStl

# Расширения файлов, за которыми ведётся наблюдение.
_WATCHED_EXTENSIONS = frozenset(('.stl', '.scl', '.awl'))


# ---------------------------------------------------------------------------
# Watchdog handler
# ---------------------------------------------------------------------------
class _CodeChangeHandler(FileSystemEventHandler):
    """Фильтрует события ``on_modified`` по расширению и делегирует
    обработку debounce-callback'у в основном узле.
    """

    def __init__(
        self,
        on_file_changed: callable,
        logger,
    ) -> None:
        super().__init__()
        self._on_file_changed = on_file_changed
        self._logger = logger

    def on_modified(self, event) -> None:  # noqa: D401
        if event.is_directory:
            return
        _, ext = os.path.splitext(event.src_path)
        if ext.lower() not in _WATCHED_EXTENSIONS:
            return
        self._logger.debug(f'FS event: modified {event.src_path}')
        self._on_file_changed(event.src_path)


# ---------------------------------------------------------------------------
# Lifecycle Node
# ---------------------------------------------------------------------------
class CodeMonitorNode(LifecycleNode):
    """Управляемый ROS 2 узел мониторинга изменений кода в реальном времени."""

    def __init__(self, **kwargs) -> None:
        super().__init__('code_monitor_node', **kwargs)

        # --- Параметры (объявляются в конструкторе, чтобы были видны
        #     в ros2 param list сразу после запуска ноды) ---
        self.declare_parameter('source_mode', 'debug_file')
        self.declare_parameter(
            'watch_directory',
            '/root/ros2_ws/src/sens_analytics/test_code',
        )
        self.declare_parameter('debounce_seconds', 0.7)

        # --- Внутреннее состояние (инициализируется в on_configure) ---
        self._parse_client: rclpy.client.Client | None = None
        self._observer: Observer | None = None
        self._debounce_timers: dict[str, threading.Timer] = {}
        self._debounce_lock = threading.Lock()
        self._debounce_sec: float = 0.7

    # ------------------------------------------------------------------
    # Lifecycle callbacks
    # ------------------------------------------------------------------
    def on_configure(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('Configuring CodeMonitorNode…')

        self._debounce_sec = (
            self.get_parameter('debounce_seconds')
            .get_parameter_value()
            .double_value
        )

        # Создаём ROS 2 клиент для сервиса /sens/parse_code
        self._parse_client = self.create_client(
            ParseStl, '/sens/parse_code',
        )

        self.get_logger().info(
            f'Service client for /sens/parse_code created. '
            f'Debounce window: {self._debounce_sec}s',
        )
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('Activating CodeMonitorNode…')
        super().on_activate(state)

        source_mode = (
            self.get_parameter('source_mode')
            .get_parameter_value()
            .string_value
        )

        if source_mode != 'debug_file':
            self.get_logger().info(
                f'source_mode="{source_mode}" — файловый мониторинг не запускается.',
            )
            return TransitionCallbackReturn.SUCCESS

        watch_dir = (
            self.get_parameter('watch_directory')
            .get_parameter_value()
            .string_value
        )

        # Гарантируем существование директории
        try:
            os.makedirs(watch_dir, exist_ok=True)
        except OSError as exc:
            self.get_logger().error(
                f'Не удалось создать watch_directory "{watch_dir}": {exc}',
            )
            return TransitionCallbackReturn.FAILURE

        handler = _CodeChangeHandler(
            on_file_changed=self._schedule_debounce,
            logger=self.get_logger(),
        )

        self._observer = Observer()
        self._observer.schedule(handler, watch_dir, recursive=False)
        self._observer.start()

        self.get_logger().info(
            f'Watchdog Observer запущен. '
            f'Директория: {watch_dir} | Расширения: {_WATCHED_EXTENSIONS}',
        )
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('Deactivating CodeMonitorNode…')

        # 1. Останавливаем Observer (фоновый поток watchdog)
        self._stop_observer()

        # 2. Отменяем все ожидающие debounce-таймеры
        self._cancel_all_debounce_timers()

        super().on_deactivate(state)
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('Cleaning up CodeMonitorNode…')
        self._stop_observer()
        self._cancel_all_debounce_timers()
        if self._parse_client is not None:
            self.destroy_client(self._parse_client)
            self._parse_client = None
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('Shutting down CodeMonitorNode…')
        self._stop_observer()
        self._cancel_all_debounce_timers()
        return TransitionCallbackReturn.SUCCESS

    # ------------------------------------------------------------------
    # Debounce logic
    # ------------------------------------------------------------------
    def _schedule_debounce(self, filepath: str) -> None:
        """Сбрасывает (или создаёт) debounce-таймер для *filepath*.

        Если файл изменяется повторно до истечения таймера — предыдущий
        таймер отменяется и запускается новый.  Таким образом, реальный
        вызов сервиса происходит только спустя ``_debounce_sec`` секунд
        *после последнего* события.
        """
        with self._debounce_lock:
            existing = self._debounce_timers.pop(filepath, None)
            if existing is not None:
                existing.cancel()

            timer = threading.Timer(
                self._debounce_sec,
                self._on_debounce_fired,
                args=(filepath,),
            )
            timer.daemon = True
            self._debounce_timers[filepath] = timer
            timer.start()

    def _on_debounce_fired(self, filepath: str) -> None:
        """Вызывается после стабилизации файла — читает его и отправляет
        на анализ через ROS 2 сервис.
        """
        # Убираем отработавший таймер из реестра
        with self._debounce_lock:
            self._debounce_timers.pop(filepath, None)

        self.get_logger().info(
            f'Debounce завершён — обработка файла: {filepath}',
        )

        # --- Чтение файла (с защитой от ошибок) ---
        try:
            with open(filepath, encoding='utf-8') as fh:
                code_text = fh.read()
        except Exception as exc:
            self.get_logger().warn(
                f'Ошибка чтения файла "{filepath}": {exc}. '
                'Пропускаем, продолжаем наблюдение.',
            )
            return

        if not code_text.strip():
            self.get_logger().warn(
                f'Файл "{filepath}" пуст или содержит только пробелы. '
                'Пропускаем вызов сервиса.',
            )
            return

        # --- Вызов сервиса /sens/parse_code ---
        self._call_parse_service(filepath, code_text)

    # ------------------------------------------------------------------
    # Service interaction
    # ------------------------------------------------------------------
    def _call_parse_service(self, filepath: str, code_text: str) -> None:
        """Асинхронно вызывает ``/sens/parse_code`` и обрабатывает ответ."""
        if self._parse_client is None:
            self.get_logger().error(
                'Service client не инициализирован (узел не сконфигурирован?).',
            )
            return

        if not self._parse_client.service_is_ready():
            self.get_logger().warn(
                'Сервис /sens/parse_code недоступен. '
                'Ожидание 2 сек…',
            )
            if not self._parse_client.wait_for_service(timeout_sec=2.0):
                self.get_logger().error(
                    'Сервис /sens/parse_code не стал доступен за 2 сек. '
                    f'Файл "{filepath}" не обработан.',
                )
                return

        request = ParseStl.Request()
        request.stl_code_text = code_text

        self.get_logger().info(
            f'Отправка {len(code_text)} символов из "{os.path.basename(filepath)}" '
            f'→ /sens/parse_code',
        )

        try:
            future = self._parse_client.call_async(request)
            future.add_done_callback(
                lambda fut: self._parse_response_callback(fut, filepath),
            )
        except Exception as exc:
            self.get_logger().error(
                f'Исключение при вызове сервиса: {exc}',
            )

    def _parse_response_callback(self, future, filepath: str) -> None:
        """Обработка ответа от сервиса ``/sens/parse_code``."""
        try:
            response: ParseStl.Response = future.result()
        except Exception as exc:
            self.get_logger().error(
                f'Ошибка получения ответа от /sens/parse_code: {exc}',
            )
            return

        if response.success:
            self.get_logger().info(
                f'[✓] Граф успешно обновлен '
                f'(файл: {os.path.basename(filepath)}, '
                f'json длина: {len(response.json_graph_output)})',
            )
        else:
            self.get_logger().warn(
                f'[✗] Сервис вернул ошибку для "{os.path.basename(filepath)}": '
                f'{response.message}',
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _stop_observer(self) -> None:
        """Безопасная остановка watchdog Observer."""
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=5.0)
            except Exception as exc:
                self.get_logger().warn(
                    f'Ошибка при остановке Observer: {exc}',
                )
            finally:
                self._observer = None

    def _cancel_all_debounce_timers(self) -> None:
        """Отменяет все ожидающие debounce-таймеры."""
        with self._debounce_lock:
            for path, timer in self._debounce_timers.items():
                timer.cancel()
                self.get_logger().debug(
                    f'Debounce-таймер отменён для: {path}',
                )
            self._debounce_timers.clear()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = CodeMonitorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
