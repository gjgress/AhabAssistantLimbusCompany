"""Windows platform services implementation."""

import ctypes
from ctypes import wintypes
from typing import Optional

import numpy as np
import win32gui
import win32ui
from PIL import Image

from module.platform.base import WindowService, CaptureService, InputService, WindowInfo, WindowRect, Result
from module.config import cfg
from module.logger import log


class WindowsWindowService(WindowService):
    """Windows window management using Win32 API."""

    def __init__(self):
        self._hwnd: Optional[int] = None

    def find_game_window(self) -> Result[WindowInfo]:
        """Find game window by title."""
        title = cfg.get_value("game_title_name", "LimbusCompany")
        hwnd = win32gui.FindWindow(None, title)

        if hwnd == 0:
            return Result.err(f"Window not found: {title}")

        self._hwnd = hwnd

        # Get window info
        rect = win32gui.GetWindowRect(hwnd)
        is_active = win32gui.GetForegroundWindow() == hwnd

        window_info = WindowInfo(
            window_id=hwnd,
            title=title,
            rect=WindowRect(x=rect[0], y=rect[1], width=rect[2] - rect[0], height=rect[3] - rect[1]),
            is_active=is_active,
        )

        return Result.ok(window_info)

    def activate_window(self, window_id: int) -> Result[bool]:
        """Activate window using Win32 API."""
        try:
            if win32gui.IsIconic(window_id):
                win32gui.ShowWindow(window_id, 9)  # SW_RESTORE
            win32gui.SetForegroundWindow(window_id)
            return Result.ok(True)
        except Exception as e:
            return Result.err(f"Failed to activate window: {e}")

    def get_window_geometry(self, window_id: int) -> Result[WindowRect]:
        """Get window geometry."""
        try:
            rect = win32gui.GetWindowRect(window_id)
            return Result.ok(WindowRect(x=rect[0], y=rect[1], width=rect[2] - rect[0], height=rect[3] - rect[1]))
        except Exception as e:
            return Result.err(f"Failed to get window geometry: {e}")

    def is_window_valid(self, window_id: int) -> bool:
        """Check if window exists."""
        return win32gui.IsWindow(window_id)


class WindowsCaptureService(CaptureService):
    """Windows screen capture using GDI."""

    def __init__(self, window_service: WindowsWindowService):
        self.window = window_service

    def capture_window(self, window_id: int) -> Result[np.ndarray]:
        """Capture window using Win32 GDI."""
        try:
            # Get window DC
            hwndDC = win32gui.GetWindowDC(window_id)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()

            # Get window size
            rect = win32gui.GetWindowRect(window_id)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]

            # Create bitmap
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)

            # Copy screen to bitmap
            ctypes.windll.user32.PrintWindow(window_id, saveDC.GetSafeHdc(), 3)

            # Convert to numpy array
            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)

            import cv2

            img = np.frombuffer(bmpstr, dtype=np.uint8)
            img.shape = (height, width, 4)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            # Cleanup
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(window_id, hwndDC)

            return Result.ok(img)

        except Exception as e:
            return Result.err(f"Failed to capture window: {e}")

    def capture_region(self, x: int, y: int, width: int, height: int) -> Result[np.ndarray]:
        """Capture screen region using Win32 GDI."""
        try:
            # Get desktop DC
            hdesktop = win32gui.GetDesktopWindow()
            desktopDC = win32gui.GetWindowDC(hdesktop)
            mfcDC = win32ui.CreateDCFromHandle(desktopDC)
            saveDC = mfcDC.CreateCompatibleDC()

            # Create bitmap
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)

            # Copy region
            saveDC.BitBlt((0, 0), (width, height), mfcDC, (x, y), win32con.SRCCOPY)

            # Convert to numpy
            bmpstr = saveBitMap.GetBitmapBits(True)
            import cv2

            img = np.frombuffer(bmpstr, dtype=np.uint8)
            img.shape = (height, width, 4)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            # Cleanup
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(hdesktop, desktopDC)

            return Result.ok(img)

        except Exception as e:
            return Result.err(f"Failed to capture region: {e}")


class WindowsInputService(InputService):
    """Windows input simulation using Win32 API."""

    def __init__(self, window_service: WindowsWindowService):
        self.window = window_service

    def click(self, x: int, y: int, window_id: int) -> Result[bool]:
        """Click at window-relative coordinates."""
        try:
            # Get absolute coordinates
            rect_result = self.window.get_window_geometry(window_id)
            if not rect_result.success:
                return Result.err(f"Failed to get window geometry: {rect_result.error}")

            rect = rect_result.data
            abs_x = rect.x + x
            abs_y = rect.y + y

            # Move cursor and click
            ctypes.windll.user32.SetCursorPos(abs_x, abs_y)
            ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
            ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP

            return Result.ok(True)

        except Exception as e:
            return Result.err(f"Failed to click: {e}")

    def send_key(self, key: str, window_id: int) -> Result[bool]:
        """Send a key press."""
        try:
            # Map key to VK code (simplified)
            vk_map = {
                "enter": 0x0D,
                "esc": 0x1B,
                "space": 0x20,
            }
            vk = vk_map.get(key.lower(), ord(key.upper()))

            # Send keydown and keyup
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
            ctypes.windll.user32.keybd_event(vk, 0, 2, 0)

            return Result.ok(True)

        except Exception as e:
            return Result.err(f"Failed to send key: {e}")

    def send_keys(self, keys: str, window_id: int) -> Result[bool]:
        """Send multiple keys."""
        for key in keys:
            result = self.send_key(key, window_id)
            if not result.success:
                return result
        return Result.ok(True)
