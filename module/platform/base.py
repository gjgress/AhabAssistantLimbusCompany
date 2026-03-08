"""Platform abstraction layer for cross-platform compatibility."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Generic, TypeVar, cast
import numpy as np


@dataclass
class WindowRect:
    """Window geometry rectangle."""

    x: int
    y: int
    width: int
    height: int


@dataclass
class WindowInfo:
    """Window information."""

    window_id: int
    title: str
    rect: WindowRect
    is_active: bool = False


T = TypeVar("T")


@dataclass
class Result(Generic[T]):
    """Result type for error handling."""

    success: bool
    data: Optional[T] = None
    error: Optional[str] = None

    @staticmethod
    def ok(data: T) -> "Result[T]":
        return Result(success=True, data=data)

    @staticmethod
    def err(msg: str) -> "Result[T]":
        return Result(success=False, error=msg)

    def unwrap(self) -> T:
        """Unwrap the result or raise an exception."""
        if not self.success or self.data is None:
            raise RuntimeError(f"Result error: {self.error}")
        return cast(T, self.data)


class WindowService(ABC):
    """Abstract window management service."""

    @abstractmethod
    def find_game_window(self) -> Result[WindowInfo]:
        """Find the game window.

        Returns:
            Result containing WindowInfo if found, error message otherwise.
        """
        pass

    @abstractmethod
    def activate_window(self, window_id: int) -> Result[bool]:
        """Activate (focus) a window.

        Args:
            window_id: The window ID to activate.

        Returns:
            Result indicating success or failure.
        """
        pass

    @abstractmethod
    def get_window_geometry(self, window_id: int) -> Result[WindowRect]:
        """Get window geometry.

        Args:
            window_id: The window ID.

        Returns:
            Result containing WindowRect.
        """
        pass

    @abstractmethod
    def is_window_valid(self, window_id: int) -> bool:
        """Check if a window still exists.

        Args:
            window_id: The window ID to check.

        Returns:
            True if window exists, False otherwise.
        """
        pass


class CaptureService(ABC):
    """Abstract screen capture service."""

    @abstractmethod
    def capture_window(self, window_id: int) -> Result[np.ndarray]:
        """Capture a window as numpy array.

        Args:
            window_id: The window ID to capture.

        Returns:
            Result containing BGR numpy array.
        """
        pass

    @abstractmethod
    def capture_region(self, x: int, y: int, width: int, height: int) -> Result[np.ndarray]:
        """Capture a screen region.

        Args:
            x: Left coordinate.
            y: Top coordinate.
            width: Region width.
            height: Region height.

        Returns:
            Result containing BGR numpy array.
        """
        pass


class InputService(ABC):
    """Abstract input simulation service."""

    @abstractmethod
    def click(self, x: int, y: int, window_id: int) -> Result[bool]:
        """Click at window-relative coordinates.

        Args:
            x: X coordinate relative to window.
            y: Y coordinate relative to window.
            window_id: Target window ID.

        Returns:
            Result indicating success or failure.
        """
        pass

    @abstractmethod
    def send_key(self, key: str, window_id: int) -> Result[bool]:
        """Send a key press to a window.

        Args:
            key: Key to send (e.g., 'enter', 'esc', 'a').
            window_id: Target window ID.

        Returns:
            Result indicating success or failure.
        """
        pass

    @abstractmethod
    def send_keys(self, keys: str, window_id: int) -> Result[bool]:
        """Send multiple key presses.

        Args:
            keys: String of keys to send.
            window_id: Target window ID.

        Returns:
            Result indicating success or failure.
        """
        pass


class PlatformServices:
    """Container for all platform services."""

    def __init__(self, window: WindowService, capture: CaptureService, input_service: InputService):
        self.window = window
        self.capture = capture
        self.input_service = input_service
