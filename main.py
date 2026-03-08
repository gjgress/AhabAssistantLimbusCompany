import os
import socket
import sys
import threading

from app.language_manager import LanguageManager
from app.my_app import MainWindow
from module.config import cfg

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication


# 创建一个辅助类用于在主线程处理信号
class ArgumentSignaler(QObject):
    arguments_received = Signal(list)


def set_working_directory() -> None:
    """Set cwd to the app directory for consistent relative paths."""
    os.chdir(
        os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    )


def configure_process_dpi() -> None:
    """Configure DPI awareness on Windows only."""
    if sys.platform != "win32":
        return

    try:
        from ctypes import windll
    except ImportError:
        return

    try:
        windll.user32.SetProcessDpiAwarenessContext(-4)
    except (AttributeError, OSError):
        try:
            windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def ensure_privileges() -> int:
    """Request elevation on Windows when needed.

    Returns:
        0 if startup should continue.
        Non-zero if the process should exit immediately.
    """
    if sys.platform != "win32":
        return 0

    try:
        import pyuac
    except ImportError:
        return 0

    if pyuac.isUserAdmin():
        return 0

    try:
        pyuac.runAsAdmin(False)
        return 1
    except Exception:
        return 1


def start_socket_server(port, signaler):
    """后台线程：监听新实例发来的参数"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", port))
        s.listen(5)
        while True:
            conn, addr = s.accept()
            with conn:
                data = conn.recv(1024).decode("utf-8")
                if data:
                    # 收到参数后通过信号发送给主线程处理
                    signaler.arguments_received.emit(data.split("|"))


def send_args_to_existing_instance(port, args):
    """尝试将参数发送给已存在的实例"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)  # 设置 1 秒超时
            s.connect(("127.0.0.1", port))
            s.sendall("|".join(args).encode("utf-8"))
        return True
    except ConnectionRefusedError:
        return False
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv

    set_working_directory()
    configure_process_dpi()

    exit_code = ensure_privileges()
    if exit_code != 0:
        return exit_code

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)

    app_port = 62333

    if send_args_to_existing_instance(app_port, argv[1:]):
        return 0

    zoom_scale = cfg.zoom_scale
    if isinstance(zoom_scale, (int, float)) and zoom_scale != 0:
        os.environ["QT_SCALE_FACTOR"] = str(zoom_scale / 100)

    lang_manager = LanguageManager()
    lang = lang_manager.init_language()

    app = QApplication(argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)

    ui = MainWindow(argv)
    signaler = ArgumentSignaler()

    def handle_args(args):
        args.insert(0, "aalc")
        ui.command_start(args)
        ui.showNormal()
        ui.activateWindow()
        ui.raise_()

    signaler.arguments_received.connect(handle_args)

    try:
        threading.Thread(target=start_socket_server, args=(app_port, signaler), daemon=True).start()
    except OSError:
        return 1

    QTimer.singleShot(50, lambda: lang_manager.set_language(lang))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
