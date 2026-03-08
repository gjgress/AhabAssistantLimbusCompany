"""Platform service factory and detection."""

import sys
from typing import Optional

from module.platform.base import PlatformServices
from module.logger import log


# Cache for platform services
_services: Optional[PlatformServices] = None


def get_platform_services() -> PlatformServices:
    """Get platform-specific services (singleton).

    Returns:
        PlatformServices instance for current platform.

    Raises:
        RuntimeError: If platform is not supported.
    """
    global _services

    if _services is not None:
        return _services

    if sys.platform == "win32":
        _services = _create_windows_services()
    elif sys.platform == "linux":
        _services = _create_linux_services()
    else:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")

    log.info(f"Initialized platform services for {sys.platform}")
    return _services


def _create_windows_services() -> PlatformServices:
    """Create Windows platform services."""
    from module.platform.windows import WindowsWindowService, WindowsCaptureService, WindowsInputService

    window_service = WindowsWindowService()
    capture_service = WindowsCaptureService(window_service)
    input_service = WindowsInputService(window_service)

    return PlatformServices(window_service, capture_service, input_service)


def _create_linux_services() -> PlatformServices:
    """Create Linux X11 platform services."""
    from module.platform.linux_x11 import X11WindowService, X11CaptureService, X11InputService

    window_service = X11WindowService()
    capture_service = X11CaptureService(window_service)
    input_service = X11InputService(window_service)

    return PlatformServices(window_service, capture_service, input_service)


def is_windows() -> bool:
    """Check if running on Windows."""
    return sys.platform == "win32"


def is_linux() -> bool:
    """Check if running on Linux."""
    return sys.platform == "linux"
