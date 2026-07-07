"""Lifecycle source node that watches a directory for ``.stl`` changes.

One of the four data-source nodes orchestrated by ``source_lifecycle_manager``.
When activated in ``debug_file`` mode it uses ``watchdog`` to observe a directory
and publishes the *actual file content* of changed ``.stl`` files to
``/sens/raw_code_stream`` (``std_msgs/String``).

Rapid IDE save storms are coalesced by a per-file debounce timer, so the
downstream ``code_bridge_node`` / ``/sens/parse_code`` service is called only
once after a file has stabilised. Pending timers and the watchdog observer
thread are torn down on ``on_deactivate`` / ``on_shutdown`` to avoid leaks.
"""

from __future__ import annotations

import os
import threading

import rclpy
from rclpy.lifecycle import Node, Publisher, State, TransitionCallbackReturn
from std_msgs.msg import String
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Расширения файлов, которые читаются и публикуются целиком.
_WATCHED_EXTENSIONS = (".stl", ".scl", ".awl")


class CodeFileHandler(FileSystemEventHandler):
    """Filter FS events by extension and forward the *filepath* to debounce."""

    def __init__(self, on_file_changed, logger):
        super().__init__()
        self._on_file_changed = on_file_changed
        self._logger = logger

    def on_modified(self, event) -> None:
        if event.is_directory:
            return
        if not event.src_path.lower().endswith(_WATCHED_EXTENSIONS):
            return
        self._logger.info(f"Detected modification in: {event.src_path}")
        # Передаём путь, а не содержимое — чтение происходит после debounce,
        # чтобы забрать финальную (устоявшуюся) версию файла.
        self._on_file_changed(event.src_path)


class FileWatcherNode(Node):
    def __init__(self):
        super().__init__("file_watcher_node")
        self.pub_: Publisher = None
        self.observer = None

        # --- Параметры (объявляем здесь, чтобы были видны в ros2 param list) ---
        self.declare_parameter("watch_dir", "/tmp/code_debug/")
        self.declare_parameter("debounce_seconds", 0.7)

        # --- Debounce-состояние ---
        self._debounce_sec: float = 0.7
        self._debounce_timers: dict[str, threading.Timer] = {}
        self._debounce_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle callbacks
    # ------------------------------------------------------------------
    def on_configure(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("FSM Transition: Configuring FileWatcherNode...")
        self.pub_ = self.create_lifecycle_publisher(String, "/sens/raw_code_stream", 10)

        self.watch_dir = self.get_parameter("watch_dir").get_parameter_value().string_value
        self._debounce_sec = (
            self.get_parameter("debounce_seconds").get_parameter_value().double_value
        )

        # Гарантируем существование директории наблюдения.
        try:
            os.makedirs(self.watch_dir, exist_ok=True)
        except OSError as exc:
            self.get_logger().error(f"Cannot create watch_dir '{self.watch_dir}': {exc}")
            return TransitionCallbackReturn.FAILURE
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("FSM Transition: Activating FileWatcherNode (debug_file mode)...")
        super().on_activate(state)

        handler = CodeFileHandler(self._schedule_debounce, self.get_logger())
        self.observer = Observer()
        self.observer.schedule(handler, self.watch_dir, recursive=False)
        self.observer.start()

        self.get_logger().info(
            f"Watchdog Observer started | dir: {self.watch_dir} | "
            f"extensions: {_WATCHED_EXTENSIONS} | debounce: {self._debounce_sec}s"
        )
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("FSM Transition: Deactivating FileWatcherNode... Going to sleep.")
        self._stop_observer()
        self._cancel_all_debounce_timers()
        super().on_deactivate(state)
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("FSM Transition: Cleaning up FileWatcherNode...")
        self._stop_observer()
        self._cancel_all_debounce_timers()
        if self.pub_:
            self.destroy_publisher(self.pub_)
            self.pub_ = None
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("FSM Transition: Shutting down FileWatcherNode...")
        self._stop_observer()
        self._cancel_all_debounce_timers()
        return TransitionCallbackReturn.SUCCESS

    # ------------------------------------------------------------------
    # Debounce logic
    # ------------------------------------------------------------------
    def _schedule_debounce(self, filepath: str) -> None:
        """Reset (or create) the debounce timer for *filepath*.

        Repeated saves before the window elapses cancel the previous timer and
        start a new one, so the file is read only once after it stabilises.
        """
        with self._debounce_lock:
            existing = self._debounce_timers.pop(filepath, None)
            if existing is not None:
                existing.cancel()

            timer = threading.Timer(
                self._debounce_sec, self._publish_file, args=(filepath,)
            )
            timer.daemon = True
            self._debounce_timers[filepath] = timer
            timer.start()

    def _publish_file(self, filepath: str) -> None:
        """Read the stabilised file from disk and publish it."""
        # Убираем отработавший таймер из реестра.
        with self._debounce_lock:
            self._debounce_timers.pop(filepath, None)

        try:
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
        except Exception as exc:
            self.get_logger().warn(f"Failed to read {filepath}: {exc}")
            return

        if not content.strip():
            self.get_logger().warn(f"File {filepath} is empty — skipping.")
            return

        # Публикуем данные ТОЛЬКО если узел активирован.
        if self.pub_ and self.pub_.is_activated:
            msg = String()
            msg.data = content
            self.pub_.publish(msg)
            self.get_logger().info(
                f"Published {len(content)} chars from {os.path.basename(filepath)} "
                f"to /sens/raw_code_stream"
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _stop_observer(self) -> None:
        if self.observer is not None:
            try:
                self.observer.stop()
                self.observer.join(timeout=5.0)
            except Exception as exc:
                self.get_logger().warn(f"Error stopping Observer: {exc}")
            finally:
                self.observer = None

    def _cancel_all_debounce_timers(self) -> None:
        with self._debounce_lock:
            for path, timer in self._debounce_timers.items():
                timer.cancel()
                self.get_logger().debug(f"Debounce timer cancelled for: {path}")
            self._debounce_timers.clear()


def main(args=None):
    rclpy.init(args=args)
    node = FileWatcherNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
