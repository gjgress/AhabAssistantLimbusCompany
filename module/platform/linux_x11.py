"""Linux X11 platform services implementation."""

import re
import subprocess
from typing import List, Optional, Tuple

import numpy as np
from Xlib import X, display
from Xlib.protocol import event
from ewmh import EWMH

from module.platform.base import WindowService, CaptureService, InputService, WindowInfo, WindowRect, Result
from module.logger import log


class X11WindowService(WindowService):
    """Linux X11 window management using python-xlib and EWMH."""

    # Fixed Steam AppID for Limbus Company
    STEAM_APP_ID = 1973530
    # Fallback window title
    FALLBACK_TITLE = "LimbusCompany"

    def __init__(self):
        try:
            self.display = display.Display()
            self.root = self.display.screen().root
            self.ewmh = EWMH(self.display, self.root)
            log.info("X11 display initialized")
        except Exception as e:
            log.error(f"Failed to initialize X11 display: {e}")
            raise RuntimeError(f"Cannot connect to X11 display: {e}")

    def find_game_window(self) -> Result[WindowInfo]:
        """Find game window using Steam AppID or window title."""
        try:
            windows = self._get_all_windows()
            log.debug(f"Checking {len(windows)} windows for game")

            # First pass: find the best matching window by size
            best_window = None
            best_size = 0

            for win_id in windows:
                # Check if window is mapped and visible
                try:
                    window = self.display.create_resource_object("window", win_id)
                    geom = window.get_geometry()

                    # Skip tiny windows (< 100 pixels in any dimension)
                    if geom.width < 100 or geom.height < 100:
                        continue

                    # Calculate window area
                    area = geom.width * geom.height

                    # Strategy 1: Check STEAM_GAME atom
                    steam_game = self._get_steam_game_property(win_id)
                    if steam_game == self.STEAM_APP_ID and area > best_size:
                        best_window = win_id
                        best_size = area
                        log.info(f"Found candidate via STEAM_GAME atom: {win_id} ({geom.width}x{geom.height})")
                        continue

                    # Strategy 2: Check WM_CLASS for steam_app_ID
                    wm_class = self._get_wm_class(win_id)
                    if wm_class and f"steam_app_{self.STEAM_APP_ID}" in wm_class and area > best_size:
                        best_window = win_id
                        best_size = area
                        log.info(f"Found candidate via WM_CLASS: {win_id} ({geom.width}x{geom.height})")
                        continue

                    # Strategy 3: Check window title (fallback)
                    title = self._get_net_wm_name(win_id)
                    if title == self.FALLBACK_TITLE and area > best_size:
                        best_window = win_id
                        best_size = area
                        log.info(f"Found candidate via title: {win_id} ({geom.width}x{geom.height})")

                except:
                    continue

            if best_window:
                log.info(f"Selected best game window: {best_window}")
                return self._create_window_info(best_window)

            return Result.err(
                f"Game window not found. Tried STEAM_GAME={self.STEAM_APP_ID}, "
                f"WM_CLASS=steam_app_{self.STEAM_APP_ID}, title={self.FALLBACK_TITLE}"
            )

        except Exception as e:
            log.error(f"Error finding game window: {e}")
            return Result.err(f"Error finding game window: {e}")

    def activate_window(self, window_id: int) -> Result[bool]:
        """Activate window using xdotool or EWMH."""
        try:
            # Try xdotool first (more reliable)
            result = subprocess.run(
                ["xdotool", "windowactivate", str(window_id)], capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                log.debug(f"Activated window {window_id}")
                return Result.ok(True)
            else:
                error_msg = result.stderr.strip() or "xdotool failed"
                log.warning(f"xdotool activation failed: {error_msg}")

                # Fallback to EWMH
                try:
                    window = self.display.create_resource_object("window", window_id)
                    self.ewmh.setActiveWindow(window)
                    self.display.sync()
                    log.debug(f"Activated window {window_id} via EWMH")
                    return Result.ok(True)
                except Exception as e:
                    return Result.err(f"Failed to activate window: {e}")

        except subprocess.TimeoutExpired:
            return Result.err("xdotool timeout")
        except FileNotFoundError:
            return Result.err("xdotool not found. Please install xdotool.")
        except Exception as e:
            return Result.err(f"Failed to activate window: {e}")

    def get_window_geometry(self, window_id: int) -> Result[WindowRect]:
        """Get window geometry including position and size."""
        try:
            window = self.display.create_resource_object("window", window_id)

            # Try to get the frame extents (window manager decorations)
            try:
                geom = window.get_geometry()
                # Get absolute position by traversing up the window tree
                x, y = self._get_absolute_position(window)

                width = geom.width
                height = geom.height

                # For small windows (< 100px), try to get the parent window which might be the real window
                if width < 100 or height < 100:
                    tree = window.query_tree()
                    if tree.parent and tree.parent.id != self.root.id:
                        parent = tree.parent
                        parent_geom = parent.get_geometry()
                        parent_x, parent_y = self._get_absolute_position(parent)
                        if parent_geom.width > width or parent_geom.height > height:
                            x, y = parent_x, parent_y
                            width = parent_geom.width
                            height = parent_geom.height

                return Result.ok(WindowRect(x=x, y=y, width=width, height=height))
            except Exception as e:
                return Result.err(f"Failed to get window geometry: {e}")

        except Exception as e:
            return Result.err(f"Failed to get window geometry: {e}")

    def is_window_valid(self, window_id: int) -> bool:
        """Check if window still exists."""
        try:
            window = self.display.create_resource_object("window", window_id)
            # Try to get geometry - will fail if window doesn't exist
            window.get_geometry()
            return True
        except:
            return False

    def _get_all_windows(self) -> List[int]:
        """Get all window IDs recursively."""
        windows = []

        def recurse(window):
            try:
                # Query tree to get children
                tree = window.query_tree()
                for child in tree.children:
                    windows.append(child.id)
                    recurse(child)
            except:
                pass

        recurse(self.root)
        return windows

    def _get_steam_game_property(self, window_id: int) -> Optional[int]:
        """Get STEAM_GAME atom value from window."""
        try:
            window = self.display.create_resource_object("window", window_id)
            atom = self.display.intern_atom("STEAM_GAME")

            prop = window.get_full_property(atom, X.AnyPropertyType)
            if prop and prop.value:
                # Parse the value - it's usually formatted like "STEAM_GAME(CARDINAL) = 1973530"
                value_str = str(prop.value)
                match = re.search(r"(\d+)", value_str)
                if match:
                    return int(match.group(1))

            return None
        except:
            return None

    def _get_wm_class(self, window_id: int) -> Optional[str]:
        """Get WM_CLASS property from window."""
        try:
            window = self.display.create_resource_object("window", window_id)
            wm_class = window.get_wm_class()
            if wm_class:
                # wm_class is a tuple (instance_name, class_name)
                return f"{wm_class[0]} {wm_class[1]}"
            return None
        except:
            return None

    def _get_net_wm_name(self, window_id: int) -> Optional[str]:
        """Get _NET_WM_NAME (UTF-8 window title)."""
        try:
            window = self.display.create_resource_object("window", window_id)

            # Try _NET_WM_NAME first (UTF-8)
            atom = self.display.intern_atom("_NET_WM_NAME")
            prop = window.get_full_property(atom, X.AnyPropertyType)
            if prop and prop.value:
                return prop.value.decode("utf-8", errors="ignore")

            # Fallback to WM_NAME
            wm_name = window.get_wm_name()
            if wm_name:
                return wm_name

            return None
        except:
            return None

    def _get_top_level_window(self, window_id: int) -> int:
        """Get the top-level window for a given window ID.

        If the window is small, traverse up to find the parent.
        """
        try:
            window = self.display.create_resource_object("window", window_id)
            current_id = window_id

            while True:
                try:
                    geom = window.get_geometry()
                    # If window is reasonably sized (> 200px), assume it's the game window
                    if geom.width > 200 and geom.height > 200:
                        return current_id

                    # Get parent
                    tree = window.query_tree()
                    if tree.parent and tree.parent.id != self.root.id:
                        window = tree.parent
                        current_id = tree.parent.id
                    else:
                        break
                except:
                    break

            return current_id
        except:
            return window_id

    def _get_absolute_position(self, window) -> Tuple[int, int]:
        """Get absolute screen position of a window."""
        x, y = 0, 0
        current = window

        while current:
            try:
                geom = current.get_geometry()
                x += geom.x
                y += geom.y

                # Get parent
                tree = current.query_tree()
                if tree.parent and tree.parent.id != self.root.id:
                    current = tree.parent
                else:
                    break
            except:
                break

        return x, y

    def _create_window_info(self, window_id: int) -> Result[WindowInfo]:
        """Create WindowInfo for a given window ID."""
        title = self._get_net_wm_name(window_id) or "Unknown"
        rect_result = self.get_window_geometry(window_id)

        if not rect_result.success:
            return Result.err(f"Failed to get window geometry: {rect_result.error}")

        # Check if window is active
        is_active = False
        try:
            active_window = self.ewmh.getActiveWindow()
            if active_window and active_window.id == window_id:
                is_active = True
        except:
            pass

        return Result.ok(WindowInfo(window_id=window_id, title=title, rect=rect_result.data, is_active=is_active))


class X11CaptureService(CaptureService):
    """Linux X11 screen capture using grim (Wayland) or mss (X11)."""

    def __init__(self, window_service: X11WindowService):
        self.window = window_service
        self._use_grim = False
        self._use_scrot = False
        self._use_mss = False

        # Check available capture tools
        import shutil

        if shutil.which("grim"):
            self._use_grim = True
            log.info("Using grim for Wayland capture")
        elif shutil.which("scrot"):
            self._use_scrot = True
            log.info("Using scrot for X11 capture")

        # Fallback to mss
        if not self._use_grim and not self._use_scrot:
            try:
                import mss

                self.sct = mss.mss()
                self._use_mss = True
                log.info("Using mss for X11 capture")
            except ImportError:
                log.error("mss not installed. Run: pip install mss")
                raise

    def capture_window(self, window_id: int) -> Result[np.ndarray]:
        """Capture window using grim (Wayland) or mss (X11)."""
        # Get window geometry
        geom_result = self.window.get_window_geometry(window_id)
        if not geom_result.success:
            return Result.err(f"Failed to get window geometry: {geom_result.error}")

        geom = geom_result.data

        if self._use_grim:
            return self._capture_with_grim(geom)
        else:
            return self._capture_with_mss(geom)

    def _capture_with_grim(self, geom: WindowRect) -> Result[np.ndarray]:
        """Capture using grim (Wayland)."""
        try:
            import cv2
            import tempfile
            import os

            # Create temp file for grim output
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name

            try:
                # grim uses format: "x,y widthxheight"
                region = f"{geom.x},{geom.y} {geom.width}x{geom.height}"

                result = subprocess.run(["grim", "-g", region, tmp_path], capture_output=True, text=True, timeout=10)

                if result.returncode != 0:
                    error_msg = result.stderr.strip() or "grim failed"
                    return Result.err(f"grim capture failed: {error_msg}")

                # Read the image
                img = cv2.imread(tmp_path)
                if img is None:
                    return Result.err("Failed to read captured image")

                log.debug(f"Captured with grim: {img.shape}")
                return Result.ok(img)

            finally:
                # Clean up temp file
                try:
                    os.unlink(tmp_path)
                except:
                    pass

        except Exception as e:
            log.error(f"Failed to capture with grim: {e}")
            return Result.err(f"Failed to capture with grim: {e}")

    def _capture_with_mss(self, geom: WindowRect) -> Result[np.ndarray]:
        """Capture using mss (X11)."""
        try:
            import cv2

            # Define monitor region
            monitor = {"left": geom.x, "top": geom.y, "width": geom.width, "height": geom.height}

            # Capture
            screenshot = self.sct.grab(monitor)

            # Convert to numpy array (BGRA format from mss)
            img = np.array(screenshot)

            # Convert BGRA to BGR
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            log.debug(f"Captured with mss: {img.shape}")
            return Result.ok(img)

        except Exception as e:
            log.error(f"Failed to capture with mss: {e}")
            return Result.err(f"Failed to capture with mss: {e}")

    def capture_region(self, x: int, y: int, width: int, height: int) -> Result[np.ndarray]:
        """Capture screen region using mss."""
        try:
            import cv2

            monitor = {"left": x, "top": y, "width": width, "height": height}

            screenshot = self.sct.grab(monitor)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            return Result.ok(img)

        except Exception as e:
            log.error(f"Failed to capture region: {e}")
            return Result.err(f"Failed to capture region: {e}")


class X11InputService(InputService):
    """Linux X11 input simulation using xdotool."""

    def __init__(self, window_service: X11WindowService):
        self.window = window_service
        self._check_xdotool()

    def _check_xdotool(self):
        """Check if xdotool is available."""
        try:
            subprocess.run(["xdotool", "--version"], capture_output=True, check=True)
            log.info("xdotool is available")
        except (FileNotFoundError, subprocess.CalledProcessError):
            log.error("xdotool not found. Please install xdotool.")
            raise RuntimeError("xdotool is required for input simulation")

    def click(self, x: int, y: int, window_id: int) -> Result[bool]:
        """Click at window-relative coordinates using xdotool."""
        try:
            # Activate window first
            activate_result = self.window.activate_window(window_id)
            if not activate_result.success:
                return Result.err(f"Failed to activate window: {activate_result.error}")

            # Get window absolute position
            geom_result = self.window.get_window_geometry(window_id)
            if not geom_result.success:
                return Result.err(f"Failed to get window geometry: {geom_result.error}")

            geom = geom_result.data
            abs_x = geom.x + x
            abs_y = geom.y + y

            # Move mouse and click
            subprocess.run(
                ["xdotool", "mousemove", str(abs_x), str(abs_y), "click", "1"],
                capture_output=True,
                check=True,
                timeout=5,
            )

            log.debug(f"Clicked at ({abs_x}, {abs_y})")
            return Result.ok(True)

        except subprocess.TimeoutExpired:
            return Result.err("xdotool timeout")
        except subprocess.CalledProcessError as e:
            return Result.err(f"xdotool failed: {e.stderr.decode() if e.stderr else 'unknown error'}")
        except Exception as e:
            return Result.err(f"Failed to click: {e}")

    def send_key(self, key: str, window_id: int) -> Result[bool]:
        """Send a key press using xdotool."""
        try:
            # Activate window first
            activate_result = self.window.activate_window(window_id)
            if not activate_result.success:
                return Result.err(f"Failed to activate window: {activate_result.error}")

            # Map common keys to xdotool format
            key_map = {
                "enter": "Return",
                "esc": "Escape",
                "space": "space",
                "tab": "Tab",
            }
            xdotool_key = key_map.get(key.lower(), key)

            subprocess.run(["xdotool", "key", xdotool_key], capture_output=True, check=True, timeout=5)

            log.debug(f"Sent key: {xdotool_key}")
            return Result.ok(True)

        except subprocess.TimeoutExpired:
            return Result.err("xdotool timeout")
        except subprocess.CalledProcessError as e:
            return Result.err(f"xdotool failed: {e.stderr.decode() if e.stderr else 'unknown error'}")
        except Exception as e:
            return Result.err(f"Failed to send key: {e}")

    def send_keys(self, keys: str, window_id: int) -> Result[bool]:
        """Send multiple keys using xdotool type."""
        try:
            # Activate window first
            activate_result = self.window.activate_window(window_id)
            if not activate_result.success:
                return Result.err(f"Failed to activate window: {activate_result.error}")

            subprocess.run(["xdotool", "type", keys], capture_output=True, check=True, timeout=5)

            log.debug(f"Sent keys: {keys}")
            return Result.ok(True)

        except subprocess.TimeoutExpired:
            return Result.err("xdotool timeout")
        except subprocess.CalledProcessError as e:
            return Result.err(f"xdotool failed: {e.stderr.decode() if e.stderr else 'unknown error'}")
        except Exception as e:
            return Result.err(f"Failed to send keys: {e}")
