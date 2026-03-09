import random
import sys
from time import sleep, time
from typing import overload

import pyautogui

if sys.platform == "win32":
    import win32api
    import win32con
    import win32gui
    from pywintypes import error as PyWinTypesError
else:
    win32api = None
    win32con = None
    win32gui = None
    PyWinTypesError = None
    # Import X11 modules for Linux
    try:
        from Xlib import X
        from Xlib.protocol import event as XEvent
    except ImportError:
        X = None
        XEvent = None

from module.config import cfg
from utils.singletonmeta import SingletonMeta

from ...game_and_screen import screen
from ...logger import log
from . import AbstractInput

if sys.platform == "win32":
    key_list = {
        "a": 0x41,
        "b": 0x42,
        "c": 0x43,
        "d": 0x44,
        "e": 0x45,
        "f": 0x46,
        "g": 0x47,
        "h": 0x48,
        "i": 0x49,
        "j": 0x4A,
        "k": 0x4B,
        "l": 0x4C,
        "m": 0x4D,
        "n": 0x4E,
        "o": 0x4F,
        "p": 0x50,
        "q": 0x51,
        "r": 0x52,
        "s": 0x53,
        "t": 0x54,
        "u": 0x55,
        "v": 0x56,
        "w": 0x57,
        "x": 0x58,
        "y": 0x59,
        "z": 0x5A,
        "0": 0x30,
        "1": 0x31,
        "2": 0x32,
        "3": 0x33,
        "4": 0x34,
        "5": 0x35,
        "6": 0x36,
        "7": 0x37,
        "8": 0x38,
        "9": 0x39,
        "enter": win32con.VK_RETURN,
        "esc": win32con.VK_ESCAPE,
        "space": win32con.VK_SPACE,
        "tab": win32con.VK_TAB,
        "shift": win32con.VK_SHIFT,
        "ctrl": win32con.VK_CONTROL,
        "alt": win32con.VK_MENU,
    }
else:
    # Linux key list (not used with xdotool, but needed for compatibility)
    key_list = {
        "a": 0x41,
        "b": 0x42,
        "c": 0x43,
        "d": 0x44,
        "e": 0x45,
        "f": 0x46,
        "g": 0x47,
        "h": 0x48,
        "i": 0x49,
        "j": 0x4A,
        "k": 0x4B,
        "l": 0x4C,
        "m": 0x4D,
        "n": 0x4E,
        "o": 0x4F,
        "p": 0x50,
        "q": 0x51,
        "r": 0x52,
        "s": 0x53,
        "t": 0x54,
        "u": 0x55,
        "v": 0x56,
        "w": 0x57,
        "x": 0x58,
        "y": 0x59,
        "z": 0x5A,
        "0": 0x30,
        "1": 0x31,
        "2": 0x32,
        "3": 0x33,
        "4": 0x34,
        "5": 0x35,
        "6": 0x36,
        "7": 0x37,
        "8": 0x38,
        "9": 0x39,
        "enter": 0x0D,
        "esc": 0x1B,
        "space": 0x20,
        "tab": 0x09,
        "shift": 0x10,
        "ctrl": 0x11,
        "alt": 0x12,
    }


class WinAbstractInput(AbstractInput):
    """输入接口类，定义输入方法的抽象接口
    专用于 Windows 系统, 提供了一些额外的通用方法

    Tips: 有特殊需求写在对应方法描述中
    """

    def get_mouse_position(self) -> tuple[int, int]:
        """获取鼠标当前位置

        Returns:
            tuple: 当前鼠标位置的元组 (x, y)
        """
        if sys.platform != "win32":
            # Linux: use xdotool to get mouse position
            try:
                import subprocess
                result = subprocess.run(['xdotool', 'getmouselocation'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    # Parse output like "x:123 y:456 screen:0 window:789"
                    parts = result.stdout.strip().split()
                    x = int(parts[0].split(':')[1])
                    y = int(parts[1].split(':')[1])
                    return (x, y)
            except Exception as e:
                log.debug(f"Failed to get mouse position: {e}")
            return (0, 0)
        return win32api.GetCursorPos()


class Input(WinAbstractInput, metaclass=SingletonMeta):
    """基于 `pyautogui` 的输入类, 仅支持前台操作"""

    # 禁用pyautogui的失败安全特性，防止意外中断
    pyautogui.FAILSAFE = False

    @overload
    def pos_offset(self, x: int, y: int) -> tuple[int, int]: ...
    @overload
    def pos_offset(self, pos: tuple[int, int]) -> tuple[int, int]: ...

    def pos_offset(self, *args) -> tuple[int, int]:  # type: ignore
        """根据当前窗口位置偏移点击位置"""
        if len(args) == 2:
            x, y = args
        elif isinstance(args[0], tuple):
            x, y = args[0]
        else:
            raise ValueError("pos_offset 接受两个整数参数或一个包含两个整数的元组")
        real_x, real_y, _, _ = screen.handle.rect(True)
        return x + real_x, y + real_y

    def mouse_click(self, x, y, times=1, move_back=False) -> bool:
        if move_back:
            current_mouse_position = self.get_mouse_position()

        msg = f"点击位置:({x},{y})"
        log.debug(msg, stacklevel=2)
        x, y = self.pos_offset(x, y)
        for i in range(times):
            pyautogui.click(x, y)
            # 多次点击执行很快所以暂停放到循环外

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

        self.wait_pause()

        return True

    def mouse_drag_down(self, x, y, reverse=1, move_back=True) -> None:
        if move_back:
            current_mouse_position = self.get_mouse_position()

        scale = cfg.set_win_size / 1080
        x, y = self.pos_offset(x, y)
        pyautogui.moveTo(x, y)
        pyautogui.mouseDown()
        pyautogui.dragTo(x, y + int(300 * scale * reverse), duration=0.4)
        pyautogui.mouseUp()

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

    def mouse_drag(self, x, y, drag_time=0.1, dx=0, dy=0, move_back=True) -> None:
        if move_back:
            current_mouse_position = self.get_mouse_position()
        x, y = self.pos_offset(x, y)
        pyautogui.moveTo(x, y)
        pyautogui.mouseDown()
        pyautogui.moveTo(x + dx, y + dy, duration=drag_time)
        if drag_time * 0.3 > 0.5:
            sleep(drag_time * 0.3)
        else:
            sleep(0.5)
        pyautogui.mouseUp()

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

    def mouse_scroll(self, direction: int = -3) -> bool:
        if direction <= 0:
            msg = "鼠标滚动滚轮，远离界面"
        else:
            msg = "鼠标滚动滚轮，拉近界面"
        log.debug(msg, stacklevel=2)
        pyautogui.scroll(direction)
        return True

    def mouse_click_blank(self, coordinate=(1, 1), times=1, move_back=False) -> bool:
        if move_back:
            current_mouse_position = self.get_mouse_position()

        msg = "点击（1，1）空白位置"
        log.debug(msg, stacklevel=2)
        x = coordinate[0] + random.randint(0, 10)
        y = coordinate[1] + random.randint(0, 10)
        x, y = self.pos_offset(x, y)
        for i in range(times):
            pyautogui.click(x, y)

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

        self.wait_pause()
        return True

    def mouse_to_blank(self, coordinate=(1, 1), move_back=False) -> None:
        if move_back:
            current_mouse_position = self.get_mouse_position()

        msg = "鼠标移动到空白，避免遮挡"
        log.debug(msg, stacklevel=2)
        pyautogui.moveTo(coordinate[0], coordinate[1])

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)
        self.wait_pause()

    def mouse_move(self, coordinate=(1, 1)) -> None:
        """鼠标移动到指定坐标

        Args:
            coordinate (tuple): 坐标元组 (x, y)
        """
        pyautogui.moveTo(coordinate[0], coordinate[1])
        self.wait_pause()

    def mouse_drag_link(self, position: list, drag_time=0.1, move_back=False) -> None:
        if move_back:
            current_mouse_position = self.get_mouse_position()

        x, y = self.pos_offset(position[0][0], position[0][1])
        pyautogui.moveTo(x, y)
        pyautogui.mouseDown()
        for pos in position:
            x, y = self.pos_offset(pos[0], pos[1])
            pyautogui.moveTo(x, y, duration=drag_time)
        pyautogui.mouseUp()

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

    def key_press(self, key):
        return pyautogui.press(key)


class BackgroundInput(WinAbstractInput, metaclass=SingletonMeta):
    """基于 `pywin32` 的输入类, 支持后台操作
    \n 除了不支持滚轮事件, 其余同 `Input` 类
    """

    def mouse_to_blank(self, coordinate=(1, 1), move_back=True) -> None:
        """鼠标移动到空白位置，避免遮挡（然而为了避免影响用户操作，这个暂时没用）
        Args:
            coordinate (tuple): 坐标元组 (x, y)
            move_back (bool): 是否在移动后将鼠标移动回原位置
        """
        # FIXME：既不能影响用户操作，也要避免遮挡，似乎没有好办法
        # FIXME：目前是不在游戏窗口内不移动鼠标, 但是我觉得应该把这个功能集成在截图里 - 233 25.10.4
        if move_back:
            current_mouse_position = self.get_mouse_position()
            rect = screen.handle.rect(True)
            if current_mouse_position[0] > rect[2] or current_mouse_position[1] > rect[3]:
                # 在窗口右下角外
                log.debug("当前鼠标位置不在游戏窗口内，取消移动到空白", stacklevel=2)
                return
            elif current_mouse_position[0] < rect[0] or current_mouse_position[1] < rect[1]:
                # 在窗口左上角外
                log.debug("当前鼠标位置不在游戏窗口内，取消移动到空白", stacklevel=2)
                return
        self._mouse_move_to(coordinate[0], coordinate[1])

        log.debug("鼠标移动到空白，避免遮挡", stacklevel=2)

        self.wait_pause()

    def mouse_click(self, x, y, times=1, move_back=True) -> bool:
        """在指定坐标上执行点击操作

        Args:
            x (int): x坐标
            y (int): y坐标
            times (int): 点击次数
            move_back (bool): 是否在点击后将鼠标移动回原位置
        Returns:
            bool (True) : 总是返回True表示操作执行完毕
        """
        if move_back:
            current_mouse_position = self.get_mouse_position()

        msg = f"点击位置:({x},{y})"
        log.debug(msg, stacklevel=2)
        for i in range(times):
            self.set_mouse_pos(x, y)
            self.set_active()
            self.mouse_down(x, y)
            self.mouse_up(x, y)
            # 多次点击执行很快所以暂停放到循环外

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

        self.wait_pause()

        return True

    def mouse_drag_down(self, x, y, reverse=1, move_back=True) -> None:
        """鼠标从指定位置向下拖动

        Args:
            x (int): x坐标
            y (int): y坐标
            reverse (int): 拖动方向，1表示向下，-1表示向上
            move_back (bool): 是否在拖动后将鼠标移动回原位置
        """
        if move_back:
            current_mouse_position = self.get_mouse_position()

        scale = cfg.set_win_size / 1080
        self.set_active()
        self.set_mouse_pos(x, y)
        self.mouse_down(x, y)
        self.set_mouse_pos(x, y + int(300 * scale * reverse), duration=0.4)
        self.mouse_up(x, y)

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

    def mouse_drag(self, x, y, drag_time=0.1, dx=0, dy=0, move_back=True) -> None:
        """鼠标从指定位置拖动到另一个位置
        Args:
            x (int): 起始x坐标
            y (int): 起始y坐标
            drag_time (float): 拖动时间
            dx (int): x方向拖动距离
            dy (int): y方向拖动距离
            move_back (bool): 是否在拖动后将鼠标移动回原位置
        """
        if move_back:
            current_mouse_position = self.get_mouse_position()
        self.set_mouse_pos(x, y)
        self.set_active()
        self.mouse_down(x, y)
        self.set_mouse_pos(x + dx, y + dy, duration=drag_time)
        if drag_time * 0.3 > 0.5:
            sleep(drag_time * 0.3)
        else:
            sleep(0.5)
        self.mouse_up(x, y)

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

    def mouse_scroll(self, direction: int = -3) -> bool:
        """
        不支持的方法\n
        进行鼠标滚动操作
        Args:
            direction (int): 滚动方向，正值表示拉近，负值表示缩小
        Returns:
            bool (False) : 表示是否支持该操作
        """
        # 不支持的方法
        return False

    def mouse_click_blank(self, coordinate=(1, 1), times=1, move_back=True) -> bool:
        """在空白位置点击鼠标
        Args:
            coordinate (tuple): 坐标元组 (x, y)
            times (int): 点击次数
            move_back (bool): 是否在点击后将鼠标移动回原位置
        Returns:
            bool (True) : 总是返回True表示操作执行完毕
        """
        if move_back:
            current_mouse_position = self.get_mouse_position()

        msg = "点击（1，1）空白位置"
        log.debug(msg, stacklevel=2)
        x = coordinate[0] + random.randint(0, 10)
        y = coordinate[1] + random.randint(0, 10)
        for i in range(times):
            self.set_mouse_pos(x, y)
            self.set_active()
            self.mouse_down(x, y)
            self.mouse_up(x, y)

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

        self.wait_pause()
        return True

    def mouse_drag_link(self, position: list, drag_time=0.1, move_back=True) -> None:
        """鼠标从指定位置拖动到指定位置
        Args:
            x (int): 起始x坐标
            y (int): 起始y坐标
            position (list): 目标位置列表
            drag_time (float): 拖动时间
        """
        if move_back:
            current_mouse_position = self.get_mouse_position()

        self.set_mouse_pos(position[0][0], position[0][1])
        self.set_active()
        self.mouse_down(position[0][0], position[0][1])
        for pos in position:
            self.set_mouse_pos(pos[0], pos[1], duration=drag_time)
        self.mouse_up(position[-1][0], position[-1][1])

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

    def set_active(self):
        """将游戏窗口设置为输入焦点以让 Unity 接受输入事件"""
        hwnd = screen.handle.hwnd
        if hwnd:
            # 如果最小化则显示
            if screen.handle.isMinimized:
                screen.handle.set_window_transparent()
                screen.handle.restore()
                sleep(0.5)

            if sys.platform != "win32":
                # Linux: activate window using xdotool or EWMH
                try:
                    from module.platform import get_platform_services
                    services = get_platform_services()
                    services.window.activate_window(hwnd)
                except Exception as e:
                    log.debug(f"Failed to activate window: {e}")
                return

            # 设置窗口的输入状态
            win32gui.EnableWindow(hwnd, True)

            # 发送激活消息（但不改变Z序）
            win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)

            # 设置焦点状态
            win32gui.SendMessage(hwnd, win32con.WM_SETFOCUS, 0, 0)
        else:
            log.error("未初始化hwnd")

    def _x11_send_mouse_button(self, window_id: int, x: int, y: int, button: int, press: bool):
        """Send mouse button event using X11 (Linux only).
        
        Args:
            window_id: X11 window ID
            x: X coordinate relative to window
            y: Y coordinate relative to window  
            button: Button number (1=left, 2=middle, 3=right)
            press: True for press, False for release
        """
        try:
            from Xlib import X
            from Xlib.display import Display
            
            display = Display()
            window = display.create_resource_object('window', window_id)
            
            # Get window position for absolute coordinates
            geom = window.get_geometry()
            tree = window.query_tree()
            abs_x = geom.x
            abs_y = geom.y
            parent = tree.parent
            while parent and parent.id != display.screen().root.id:
                parent_geom = parent.get_geometry()
                abs_x += parent_geom.x
                abs_y += parent_geom.y
                tree = parent.query_tree()
                parent = tree.parent
            
            # Calculate absolute position
            root_x = abs_x + x
            root_y = abs_y + y
            
            # Create the event
            if press:
                x11_event = XEvent.ButtonPress(
                    time=X.CurrentTime,
                    root=display.screen().root,
                    window=window,
                    child=X.NONE,
                    root_x=root_x,
                    root_y=root_y,
                    event_x=x,
                    event_y=y,
                    state=0,
                    detail=button,
                    same_screen=True
                )
            else:
                x11_event = XEvent.ButtonRelease(
                    time=X.CurrentTime,
                    root=display.screen().root,
                    window=window,
                    child=X.NONE,
                    root_x=root_x,
                    root_y=root_y,
                    event_x=x,
                    event_y=y,
                    state=0,
                    detail=button,
                    same_screen=True
                )
            
            # Send the event
            window.send_event(x11_event, propagate=False, event_mask=X.ButtonPressMask if press else X.ButtonReleaseMask)
            display.sync()
            display.close()
            
        except Exception as e:
            log.debug(f"X11 mouse event failed: {e}, falling back to xdotool")
            # Fallback to xdotool
            import subprocess
            abs_x, abs_y = self._get_absolute_coords(window_id, x, y)
            if press:
                subprocess.run(['xdotool', 'mousemove', str(abs_x), str(abs_y), 'mousedown', str(button)], 
                             capture_output=True, timeout=5)
            else:
                subprocess.run(['xdotool', 'mousemove', str(abs_x), str(abs_y), 'mouseup', str(button)], 
                             capture_output=True, timeout=5)
    
    def _get_absolute_coords(self, window_id: int, x: int, y: int) -> tuple:
        """Get absolute screen coordinates from window-relative coordinates."""
        try:
            from Xlib.display import Display
            display = Display()
            window = display.create_resource_object('window', window_id)
            geom = window.get_geometry()
            tree = window.query_tree()
            abs_x = geom.x + x
            abs_y = geom.y + y
            parent = tree.parent
            while parent and parent.id != display.screen().root.id:
                parent_geom = parent.get_geometry()
                abs_x += parent_geom.x
                abs_y += parent_geom.y
                tree = parent.query_tree()
                parent = tree.parent
            display.close()
            return (abs_x, abs_y)
        except:
            # Fallback: assume window is at (0,0) relative to screen
            return (x, y)

    def mouse_down(self, x, y):
        """鼠标左键按下
        Args:
            x (number): 相对于窗口左上角的 x 轴坐标
            y (number): 相对于窗口左上角的 y 轴坐标
        """
        x = int(x)
        y = int(y)
        hwnd = screen.handle.hwnd
        
        if sys.platform != "win32":
            self._x11_send_mouse_button(hwnd, x, y, 1, True)
            return
            
        long_positon = win32api.MAKELONG(x, y)
        win32api.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, 0, long_positon)
        sleep(0.01)

    def mouse_up(self, x, y):
        """鼠标左键抬起
        Args:
            x (number): 相对于窗口左上角的 x 轴坐标
            y (number): 相对于窗口左上角的 y 轴坐标
        """
        x = int(x)
        y = int(y)
        hwnd = screen.handle.hwnd
        
        if sys.platform != "win32":
            self._x11_send_mouse_button(hwnd, x, y, 1, False)
            return
            
        long_positon = win32api.MAKELONG(x, y)
        win32api.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, long_positon)
        sleep(0.01)

    def set_mouse_pos(self, x, y, duration: float = 0):
        """移动光标位置
        Args:
            x (number): 相对于窗口左上角的 x 轴坐标
            y (number): 相对于窗口左上角的 y 轴坐标
        """
        x = int(x)
        y = int(y)
        rect = screen.handle.rect(True)
        if duration <= 0:
            self._mouse_move_to(rect[0] + x, rect[1] + y)
        else:
            self._mouse_move_to(rect[0] + x, rect[1] + y, duration=duration)

    def _get_xdotool_key(self, key: str) -> str:
        """Convert key name to xdotool format."""
        key_map = {
            'enter': 'Return',
            'esc': 'Escape',
            'space': 'space',
            'tab': 'Tab',
            'shift': 'Shift',
            'ctrl': 'Control',
            'alt': 'Alt',
        }
        return key_map.get(key.lower(), key)

    def key_down(self, key: str):
        """键盘按键按下
        Args:
            key (str): 按键名称
        """
        hwnd = screen.handle.hwnd
        
        if sys.platform != "win32":
            # Linux: use xdotool for key press
            try:
                import subprocess
                xdotool_key = self._get_xdotool_key(key)
                subprocess.run(['xdotool', 'keydown', xdotool_key], 
                             capture_output=True, timeout=5)
            except Exception as e:
                log.debug(f"Key down failed: {e}")
            return
            
        lparam = 0x00000001  # 重复次数为1
        win32api.SendMessage(hwnd, win32con.WM_KEYDOWN, key_list[key.lower()], lparam)

    def key_up(self, key: str):
        """键盘按键抬起
        Args:
            key (str): 按键名称
        """
        hwnd = screen.handle.hwnd
        
        if sys.platform != "win32":
            # Linux: use xdotool for key release
            try:
                import subprocess
                xdotool_key = self._get_xdotool_key(key)
                subprocess.run(['xdotool', 'keyup', xdotool_key], 
                             capture_output=True, timeout=5)
            except Exception as e:
                log.debug(f"Key up failed: {e}")
            return
            
        lparam = 0xC0000001  # 转换状态为1（按键释放）
        win32api.SendMessage(hwnd, win32con.WM_KEYUP, key_list[key.lower()], lparam)

    def key_press(self, key):
        """一次键盘按键操作
        Args:
            key (str): 按键名称
        """
        self.set_active()
        self.key_down(key)
        self.key_up(key)

    def mouse_move(self, coordinate=(1, 1)) -> None:
        """鼠标移动到指定坐标

        Args:
            coordinate (tuple): 坐标元组 (x, y)
        """
        self._mouse_move_to(coordinate[0], coordinate[1])
        self.wait_pause()

    def _mouse_move_to(self, x, y, duration: float = 0):
        """将鼠标移动到指定位置（绝对于屏幕坐标）

        Args:
            x (int): x坐标
            y (int): y坐标
        """
        x = int(x)
        y = int(y)
        if duration <= 0:
            self._set_mouse_pos(x, y)
        else:
            start_x, start_y = self.get_mouse_position()
            steps = int(duration / 0.01)
            for i in range(steps):
                new_x = int(start_x + (x - start_x) * (i + 1) / steps)
                new_y = int(start_y + (y - start_y) * (i + 1) / steps)
                self._set_mouse_pos(new_x, new_y)
                sleep(0.01)

    def _set_mouse_pos(self, x: int, y: int):
        """将鼠标移动到指定位置（绝对于屏幕坐标）

        Args:
            x (int): x坐标
            y (int): y坐标
        """
        if sys.platform != "win32":
            # Linux: use xdotool or pyautogui
            try:
                import subprocess
                subprocess.run(['xdotool', 'mousemove', str(x), str(y)], 
                             capture_output=True, timeout=5)
            except Exception as e:
                log.debug(f"xdotool mouse move failed: {e}, falling back to pyautogui")
                pyautogui.moveTo(x, y)
            return
            
        try:
            win32api.SetCursorPos((x, y))
        except PyWinTypesError as e:
            # 奇怪的权限冲突 (183:当文件已存在时，无法创建该文件。)
            # 偶尔出现不影响使用

            log.debug(f"鼠标移动失败: {e}")
            try:
                pyautogui.moveTo(x, y)
            except Exception as e:
                log.error(f"鼠标移动失败: {type(e)}: {e}")


class WindowMoveInput(WinAbstractInput, metaclass=SingletonMeta):
    """"""

    def mouse_to_blank(self, coordinate=(1, 1), move_back=False) -> None:
        # FIXME: 移动窗口来防止遮蔽不是一个好选择
        return

    def mouse_scroll(self, direction: int = 120) -> bool:
        return False

    def mouse_drag(self, x, y, drag_time=0.1, dx=0, dy=0, move_back=True) -> None:
        pos = self._set_window_pos(x, y)
        self.set_active()
        self.mouse_down(x, y)
        self._window_move_to(x + dx, y + dy, duration=drag_time)
        if drag_time * 0.3 > 0.5:
            sleep(drag_time * 0.3)
        else:
            sleep(0.5)
        self.mouse_up(x, y)
        screen.handle.set_window_pos(*pos)

    def mouse_drag_down(self, x, y, reverse=1, move_back=True) -> None:
        scale = cfg.set_win_size / 1080
        self.set_active()
        pos = self._set_window_pos(x, y)
        self.mouse_down(x, y)
        self._window_move_to(x, y + int(500 * scale * reverse), duration=0.6)
        self.mouse_up(x, y)

        screen.handle.set_window_pos(*pos)

    def mouse_drag_link(self, position: list, drag_time=0.1, move_back=False) -> None:
        raw_pos = self._set_window_pos(position[0][0], position[0][1])
        self.set_active()
        self.mouse_down(position[0][0], position[0][1])
        for pos in position:
            self._window_move_to(pos[0], pos[1], duration=drag_time)

        self.mouse_up(position[-1][0], position[-1][1])
        screen.handle.set_window_pos(*raw_pos)

    def mouse_click_blank(self, coordinate=(1, 1), times=1, move_back=False) -> bool:
        msg = "点击（1，1）空白位置"
        log.debug(msg, stacklevel=2)
        x = coordinate[0] + random.randint(0, 10)
        y = coordinate[1] + random.randint(0, 10)
        self.mouse_click(x, y, times=times)
        return True

    def _window_move_to(self, x_or_pos: int | tuple[int, int], y: int = -32000, duration: float = 0) -> tuple[int, int]:
        if duration <= 0:
            return self._set_window_pos(x_or_pos, y)
        else:
            if isinstance(x_or_pos, tuple):
                target_x, target_y = x_or_pos
            else:
                target_x = x_or_pos
                target_y = y
        raw_pos = screen.handle.rect()[:2]
        current_x, current_y = screen.handle.mouse_pos_to_client_mouse(*self.get_mouse_position())
        accur = 7000
        duration = int(max(duration, 0.01) * accur)
        dx = (target_x - current_x) / duration * 100
        dy = (target_y - current_y) / duration * 100
        steps = duration // 100
        time_per_step = duration / steps / accur
        for index in range(steps - 1):
            start = time()
            x = int(current_x + dx * (index + 1))
            y = int(current_y + dy * (index + 1))
            self._set_window_pos(x, y)
            elapsed = time() - start
            if time_per_step - elapsed > 0.01:
                sleep(time_per_step - elapsed)

        self._set_window_pos(target_x, target_y)
        return raw_pos

    def get_mouse_position(self) -> tuple[int, int]:
        return win32api.GetCursorPos()

    @overload
    def _set_window_pos(self, x_or_pos: int, y: int) -> tuple[int, int]: ...
    @overload
    def _set_window_pos(self, x_or_pos: tuple[int, int]) -> tuple[int, int]: ...
    def _set_window_pos(
        self,
        x_or_pos: int | tuple[int, int],
        y: int = -32000,
    ) -> tuple[int, int]:
        """将窗口基于工作区左上角的指定位置移动到鼠标当前位置"""
        hwnd = screen.handle.hwnd
        if isinstance(x_or_pos, tuple):
            x, y = x_or_pos
        else:
            x = x_or_pos
        if screen.handle.isMinimized:
            screen.handle.set_window_transparent()
            screen.handle.restore()
            sleep(0.1)  # 先恢复窗口,防止被放在左上角
        original_rect = screen.handle.rect()
        mouse_pos = self.get_mouse_position()
        x = int(x)
        y = int(y)

        if cfg.set_win_position == "free":
            dx, dy = screen.handle.client_to_screen(0, 0)
        else:
            dx = 0
            dy = 0
        win32gui.SetWindowPos(
            hwnd,
            None,
            mouse_pos[0] - x + dx,
            mouse_pos[1] - y + dy,
            0,
            0,
            win32con.SWP_NOSIZE
            | win32con.SWP_NOZORDER
            | win32con.SWP_NOACTIVATE
            | win32con.SWP_NOSENDCHANGING
            | win32con.SWP_NOREDRAW,
        )

        return original_rect[:2]

    def set_active(self):
        """将游戏窗口设置为输入焦点以让 Unity 接受输入事件"""
        hwnd = screen.handle.hwnd
        if hwnd:
            # 如果最小化则显示
            if screen.handle.isMinimized:
                screen.handle.set_window_transparent()
                screen.handle.restore()
                sleep(0.5)

            if sys.platform != "win32":
                # Linux: use platform services
                try:
                    from module.platform import get_platform_services
                    services = get_platform_services()
                    services.window.activate_window(hwnd)
                except Exception as e:
                    log.debug(f"Failed to activate window: {e}")
                return

            # 发送激活消息（但不改变Z序）
            win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
        else:
            log.error("未初始化hwnd")

    def key_down(self, key: str):
        """键盘按键按下
        Args:
            key (str): 按键名称
        """
        hwnd = screen.handle.hwnd
        lparam = 0x00000001  # 重复次数为1
        win32api.SendMessage(hwnd, win32con.WM_KEYDOWN, key_list[key.lower()], lparam)

    def key_up(self, key: str):
        """键盘按键抬起
        Args:
            key (str): 按键名称
        """
        hwnd = screen.handle.hwnd
        lparam = 0xC0000001  # 转换状态为1（按键释放）
        win32api.SendMessage(hwnd, win32con.WM_KEYUP, key_list[key.lower()], lparam)

    def key_press(self, key):
        """一次键盘按键操作
        Args:
            key (str): 按键名称
        """
        self.set_active()
        self.key_down(key)
        self.key_up(key)

    def mouse_down(self, x, y):
        """鼠标左键按下
        Args:
            x (number): 相对于窗口左上角的 x 轴坐标
            y (number): 相对于窗口左上角的 y 轴坐标
        """
        x = int(x)
        y = int(y)
        hwnd = screen.handle.hwnd
        long_positon = win32api.MAKELONG(x, y)
        win32api.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, 0, long_positon)
        sleep(0.01)

    def mouse_up(self, x, y):
        """鼠标左键抬起
        Args:
            x (number): 相对于窗口左上角的 x 轴坐标
            y (number): 相对于窗口左上角的 y 轴坐标
        """
        x = int(x)
        y = int(y)
        hwnd = screen.handle.hwnd
        long_positon = win32api.MAKELONG(x, y)
        win32api.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, long_positon)
        sleep(0.01)

    def mouse_click(self, x, y, times=1, move_back=False) -> bool:
        msg = f"点击位置:({x},{y})"
        log.debug(msg, stacklevel=2)
        pos = None
        for _ in range(times):
            if not pos:
                pos = self._set_window_pos(x, y)
            else:
                self._set_window_pos(x, y)
            self.set_active()
            self.mouse_down(x, y)
            self.mouse_up(x, y)
        assert pos is not None
        screen.handle.set_window_pos(*pos)
        self.wait_pause()
        return True


class LinuxInput(AbstractInput):
    """基于 xdotool 的 Linux 前台输入类

    使用 xdotool 控制全局鼠标/键盘，适用于 X11/XWayland 环境。
    游戏窗口必须在屏幕上可见。
    """

    def __init__(self):
        super().__init__()
        self._check_xdotool()

    def _check_xdotool(self):
        """检查 xdotool 是否可用。"""
        try:
            import subprocess
            subprocess.run(['xdotool', '--version'], capture_output=True, check=True, timeout=5)
        except (FileNotFoundError, subprocess.CalledProcessError):
            raise RuntimeError("xdotool not found. Please install xdotool: sudo apt install xdotool")

    def _get_window_absolute_pos(self, x: int, y: int) -> tuple[int, int]:
        """获取相对于屏幕的绝对坐标。"""
        rect = screen.handle.rect(True)
        return (rect[0] + x, rect[1] + y)

    @overload
    def pos_offset(self, x: int, y: int) -> tuple[int, int]: ...
    @overload
    def pos_offset(self, pos: tuple[int, int]) -> tuple[int, int]: ...

    def pos_offset(self, *args) -> tuple[int, int]:  # type: ignore
        """根据当前窗口位置偏移点击位置"""
        if len(args) == 2:
            x, y = args
        elif isinstance(args[0], tuple):
            x, y = args[0]
        else:
            raise ValueError("pos_offset 接受两个整数参数或一个包含两个整数的元组")
        real_x, real_y, _, _ = screen.handle.rect(True)
        return x + real_x, y + real_y

    def mouse_click(self, x, y, times=1, move_back=False) -> bool:
        import subprocess

        if move_back:
            current_mouse_position = self.get_mouse_position()

        msg = f"点击位置:({x},{y})"
        log.debug(msg, stacklevel=2)
        x, y = self.pos_offset(x, y)

        for i in range(times):
            subprocess.run(['xdotool', 'mousemove', str(x), str(y), 'click', '1'],
                          capture_output=True, timeout=5)

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

        self.wait_pause()
        return True

    def mouse_drag_down(self, x, y, reverse=1, move_back=True) -> None:
        import subprocess

        if move_back:
            current_mouse_position = self.get_mouse_position()

        scale = cfg.set_win_size / 1080
        x, y = self.pos_offset(x, y)
        end_y = y + int(300 * scale * reverse)

        subprocess.run(['xdotool', 'mousemove', str(x), str(y), 'mousedown', '1'],
                      capture_output=True, timeout=5)
        sleep(0.4)
        subprocess.run(['xdotool', 'mousemove', str(x), str(end_y), 'mouseup', '1'],
                      capture_output=True, timeout=5)

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

    def mouse_drag(self, x, y, drag_time=0.1, dx=0, dy=0, move_back=True) -> None:
        import subprocess

        if move_back:
            current_mouse_position = self.get_mouse_position()

        x, y = self.pos_offset(x, y)
        end_x = x + dx
        end_y = y + dy

        subprocess.run(['xdotool', 'mousemove', str(x), str(y), 'mousedown', '1'],
                      capture_output=True, timeout=5)

        # Simulate drag with intermediate steps
        steps = max(int(drag_time / 0.01), 10)
        for i in range(1, steps):
            inter_x = x + (end_x - x) * i // steps
            inter_y = y + (end_y - y) * i // steps
            subprocess.run(['xdotool', 'mousemove', str(inter_x), str(inter_y)],
                          capture_output=True, timeout=5)
            sleep(drag_time / steps)

        subprocess.run(['xdotool', 'mousemove', str(end_x), str(end_y), 'mouseup', '1'],
                      capture_output=True, timeout=5)

        if drag_time * 0.3 > 0.5:
            sleep(drag_time * 0.3)
        else:
            sleep(0.5)

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

    def mouse_scroll(self, direction: int = -3) -> bool:
        import subprocess

        if direction <= 0:
            msg = "鼠标滚动滚轮，远离界面"
        else:
            msg = "鼠标滚动滚轮，拉近界面"
        log.debug(msg, stacklevel=2)

        # xdotool scroll: positive is up, negative is down
        # We invert direction to match the expected behavior
        scroll_amount = -direction
        subprocess.run(['xdotool', 'scroll', str(scroll_amount)], capture_output=True, timeout=5)
        return True

    def mouse_click_blank(self, coordinate=(1, 1), times=1, move_back=False) -> bool:
        if move_back:
            current_mouse_position = self.get_mouse_position()

        msg = "点击（1，1）空白位置"
        log.debug(msg, stacklevel=2)
        x = coordinate[0] + random.randint(0, 10)
        y = coordinate[1] + random.randint(0, 10)
        x, y = self.pos_offset(x, y)

        for i in range(times):
            subprocess.run(['xdotool', 'mousemove', str(x), str(y), 'click', '1'],
                          capture_output=True, timeout=5)

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

        self.wait_pause()
        return True

    def mouse_to_blank(self, coordinate=(1, 1), move_back=False) -> None:
        if move_back:
            current_mouse_position = self.get_mouse_position()

        msg = "鼠标移动到空白，避免遮挡"
        log.debug(msg, stacklevel=2)
        x, y = self.pos_offset(coordinate[0], coordinate[1])
        subprocess.run(['xdotool', 'mousemove', str(x), str(y)], capture_output=True, timeout=5)

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)
        self.wait_pause()

    def mouse_move(self, coordinate=(1, 1)) -> None:
        import subprocess
        x, y = self.pos_offset(coordinate[0], coordinate[1])
        subprocess.run(['xdotool', 'mousemove', str(x), str(y)], capture_output=True, timeout=5)
        self.wait_pause()

    def mouse_drag_link(self, position: list, drag_time=0.1, move_back=False) -> None:
        import subprocess

        if move_back:
            current_mouse_position = self.get_mouse_position()

        # Move to first position
        x, y = self.pos_offset(position[0][0], position[0][1])
        subprocess.run(['xdotool', 'mousemove', str(x), str(y), 'mousedown', '1'],
                      capture_output=True, timeout=5)

        # Drag through all positions
        for i, pos in enumerate(position[1:], 1):
            x, y = self.pos_offset(pos[0], pos[1])
            sleep(drag_time)
            subprocess.run(['xdotool', 'mousemove', str(x), str(y)], capture_output=True, timeout=5)

        # Release at last position
        x, y = self.pos_offset(position[-1][0], position[-1][1])
        subprocess.run(['xdotool', 'mousemove', str(x), str(y), 'mouseup', '1'],
                      capture_output=True, timeout=5)

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

    def key_press(self, key):
        import subprocess
        key_map = {
            'enter': 'Return',
            'esc': 'Escape',
            'space': 'space',
            'tab': 'Tab',
            'shift': 'Shift',
            'ctrl': 'Control',
            'alt': 'Alt',
        }
        xdotool_key = key_map.get(key.lower(), key)
        subprocess.run(['xdotool', 'key', xdotool_key], capture_output=True, timeout=5)

    def get_mouse_position(self) -> tuple[int, int]:
        import subprocess
        try:
            result = subprocess.run(['xdotool', 'getmouselocation'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Parse output like "x:123 y:456 screen:0 window:789"
                parts = result.stdout.strip().split()
                x = int(parts[0].split(':')[1])
                y = int(parts[1].split(':')[1])
                return (x, y)
        except Exception:
            pass
        return (0, 0)


class LinuxBackgroundInput(AbstractInput):
    """基于 python-xlib 的 Linux 后台输入类

    使用 X11 事件直接发送到窗口，适用于 XWayland (Proton 游戏)。
    游戏窗口可以在后台运行，但不能最小化。
    """

    def __init__(self):
        super().__init__()
        self._check_xlib()
        self.display = None
        self._init_display()

    def _check_xlib(self):
        """检查 python-xlib 是否可用。"""
        try:
            from Xlib import X
            from Xlib.display import Display
        except ImportError:
            raise RuntimeError("python-xlib not found. Please install: pip install python-xlib")

    def _init_display(self):
        """初始化 X11 显示连接。"""
        try:
            from Xlib.display import Display
            self.display = Display()
        except Exception as e:
            log.error(f"Failed to connect to X11 display: {e}")
            raise RuntimeError(f"Cannot connect to X11 display: {e}")

    def _get_window(self, window_id: int):
        """获取 X11 窗口对象。"""
        from Xlib.display import Display
        if self.display is None:
            self._init_display()
        return self.display.create_resource_object('window', window_id)

    def _get_absolute_coords(self, window_id: int, x: int, y: int) -> tuple[int, int]:
        """获取窗口内相对坐标的绝对屏幕坐标。"""
        try:
            window = self._get_window(window_id)
            geom = window.get_geometry()
            tree = window.query_tree()
            abs_x = geom.x + x
            abs_y = geom.y + y
            parent = tree.parent
            while parent and parent.id != self.display.screen().root.id:
                parent_geom = parent.get_geometry()
                abs_x += parent_geom.x
                abs_y += parent_geom.y
                tree = parent.query_tree()
                parent = tree.parent
            return (abs_x, abs_y)
        except Exception as e:
            log.debug(f"Failed to get absolute coords: {e}")
            return (x, y)

    def set_active(self):
        """将游戏窗口设置为输入焦点。"""
        hwnd = screen.handle.hwnd
        if hwnd:
            # 如果最小化则显示
            if screen.handle.isMinimized:
                screen.handle.set_window_transparent()
                screen.handle.restore()
                sleep(0.5)

            try:
                from module.platform import get_platform_services
                services = get_platform_services()
                services.window.activate_window(hwnd)
            except Exception as e:
                log.debug(f"Failed to activate window: {e}")
        else:
            log.error("未初始化hwnd")

    def _send_mouse_button(self, window_id: int, x: int, y: int, button: int, press: bool):
        """发送鼠标按钮事件到指定窗口。"""
        try:
            from Xlib import X
            from Xlib.protocol import event as XEvent

            window = self._get_window(window_id)

            # 获取窗口绝对位置
            abs_x, abs_y = self._get_absolute_coords(window_id, x, y)

            # 创建事件
            if press:
                x11_event = XEvent.ButtonPress(
                    time=X.CurrentTime,
                    root=self.display.screen().root,
                    window=window,
                    child=X.NONE,
                    root_x=abs_x,
                    root_y=abs_y,
                    event_x=x,
                    event_y=y,
                    state=0,
                    detail=button,
                    same_screen=True
                )
            else:
                x11_event = XEvent.ButtonRelease(
                    time=X.CurrentTime,
                    root=self.display.screen().root,
                    window=window,
                    child=X.NONE,
                    root_x=abs_x,
                    root_y=abs_y,
                    event_x=x,
                    event_y=y,
                    state=0,
                    detail=button,
                    same_screen=True
                )

            window.send_event(x11_event, propagate=False,
                            event_mask=X.ButtonPressMask if press else X.ButtonReleaseMask)
            self.display.sync()

        except Exception as e:
            log.debug(f"X11 mouse event failed: {e}")
            raise

    def mouse_down(self, x, y):
        """鼠标左键按下。"""
        hwnd = screen.handle.hwnd
        self._send_mouse_button(hwnd, int(x), int(y), 1, True)
        sleep(0.01)

    def mouse_up(self, x, y):
        """鼠标左键抬起。"""
        hwnd = screen.handle.hwnd
        self._send_mouse_button(hwnd, int(x), int(y), 1, False)
        sleep(0.01)

    def set_mouse_pos(self, x, y, duration: float = 0):
        """移动光标位置（Linux后台模式下不需要实际移动光标）。"""
        # 后台模式下不移动实际光标
        pass

    def _mouse_move_to(self, x: int, y: int):
        """将鼠标移动到指定位置（Linux后台模式下不需要）。"""
        pass

    def mouse_click(self, x, y, times=1, move_back=True) -> bool:
        if move_back:
            current_mouse_position = self.get_mouse_position()

        msg = f"点击位置:({x},{y})"
        log.debug(msg, stacklevel=2)

        for i in range(times):
            self.set_mouse_pos(x, y)
            self.set_active()
            self.mouse_down(x, y)
            self.mouse_up(x, y)

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

        self.wait_pause()
        return True

    def mouse_drag_down(self, x, y, reverse=1, move_back=True) -> None:
        if move_back:
            current_mouse_position = self.get_mouse_position()

        scale = cfg.set_win_size / 1080
        self.set_active()
        self.set_mouse_pos(x, y)
        self.mouse_down(x, y)
        sleep(0.4)
        end_y = y + int(300 * scale * reverse)
        self.mouse_up(x, end_y)

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

    def mouse_drag(self, x, y, drag_time=0.1, dx=0, dy=0, move_back=True) -> None:
        if move_back:
            current_mouse_position = self.get_mouse_position()

        self.set_mouse_pos(x, y)
        self.set_active()
        self.mouse_down(x, y)

        # 模拟拖动过程
        steps = max(int(drag_time / 0.01), 10)
        for i in range(1, steps):
            inter_x = x + dx * i // steps
            inter_y = y + dy * i // steps
            sleep(drag_time / steps)

        self.mouse_up(x + dx, y + dy)

        if drag_time * 0.3 > 0.5:
            sleep(drag_time * 0.3)
        else:
            sleep(0.5)

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

    def mouse_scroll(self, direction: int = -3) -> bool:
        """不支持滚轮事件。"""
        return False

    def mouse_click_blank(self, coordinate=(1, 1), times=1, move_back=True) -> bool:
        if move_back:
            current_mouse_position = self.get_mouse_position()

        msg = "点击（1，1）空白位置"
        log.debug(msg, stacklevel=2)
        x = coordinate[0] + random.randint(0, 10)
        y = coordinate[1] + random.randint(0, 10)

        for i in range(times):
            self.set_mouse_pos(x, y)
            self.set_active()
            self.mouse_down(x, y)
            self.mouse_up(x, y)

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

        self.wait_pause()
        return True

    def mouse_to_blank(self, coordinate=(1, 1), move_back=True) -> None:
        """鼠标移动到空白位置（后台模式不执行）。"""
        if move_back:
            current_mouse_position = self.get_mouse_position()
            rect = screen.handle.rect(True)
            if (current_mouse_position[0] > rect[2] or current_mouse_position[1] > rect[3] or
                current_mouse_position[0] < rect[0] or current_mouse_position[1] < rect[1]):
                log.debug("当前鼠标位置不在游戏窗口内，取消移动到空白", stacklevel=2)
                return

        self.set_mouse_pos(coordinate[0], coordinate[1])
        log.debug("鼠标移动到空白，避免遮挡", stacklevel=2)
        self.wait_pause()

    def mouse_move(self, coordinate=(1, 1)) -> None:
        import subprocess
        try:
            subprocess.run(['xdotool', 'mousemove', str(coordinate[0]), str(coordinate[1])],
                          capture_output=True, timeout=5)
        except Exception as e:
            log.debug(f"Mouse move failed: {e}")
        self.wait_pause()

    def mouse_drag_link(self, position: list, drag_time=0.1, move_back=False) -> None:
        if move_back:
            current_mouse_position = self.get_mouse_position()

        self.set_mouse_pos(position[0][0], position[0][1])
        self.set_active()
        self.mouse_down(position[0][0], position[0][1])

        for pos in position[1:]:
            sleep(drag_time)

        self.mouse_up(position[-1][0], position[-1][1])

        if move_back and current_mouse_position:
            self.mouse_move(current_mouse_position)

    def _get_xdotool_key(self, key: str) -> str:
        """转换按键名称为 xdotool 格式。"""
        key_map = {
            'enter': 'Return',
            'esc': 'Escape',
            'space': 'space',
            'tab': 'Tab',
            'shift': 'Shift',
            'ctrl': 'Control',
            'alt': 'Alt',
        }
        return key_map.get(key.lower(), key)

    def key_down(self, key: str):
        import subprocess
        try:
            xdotool_key = self._get_xdotool_key(key)
            subprocess.run(['xdotool', 'keydown', xdotool_key],
                          capture_output=True, timeout=5)
        except Exception as e:
            log.debug(f"Key down failed: {e}")

    def key_up(self, key: str):
        import subprocess
        try:
            xdotool_key = self._get_xdotool_key(key)
            subprocess.run(['xdotool', 'keyup', xdotool_key],
                          capture_output=True, timeout=5)
        except Exception as e:
            log.debug(f"Key up failed: {e}")

    def key_press(self, key):
        self.set_active()
        self.key_down(key)
        self.key_up(key)

    def get_mouse_position(self) -> tuple[int, int]:
        import subprocess
        try:
            result = subprocess.run(['xdotool', 'getmouselocation'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                parts = result.stdout.strip().split()
                x = int(parts[0].split(':')[1])
                y = int(parts[1].split(':')[1])
                return (x, y)
        except Exception:
            pass
        return (0, 0)
