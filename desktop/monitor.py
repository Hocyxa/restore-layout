import ctypes
from ctypes import wintypes
from dataclasses import dataclass

user32 = ctypes.WinDLL("user32", use_last_error=True)

MONITOR_DEFAULTTOPRIMARY = 1
MONITORINFOF_PRIMARY = 1


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
    ]


@dataclass(frozen=True, slots=True)
class Monitor:
    left: int
    top: int
    right: int
    bottom: int
    work_left: int
    work_top: int
    work_right: int
    work_bottom: int
    is_primary: bool

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def work_width(self) -> int:
        return self.work_right - self.work_left

    @property
    def work_height(self) -> int:
        return self.work_bottom - self.work_top


def get_primary_monitor() -> Monitor:
    """Получает геометрию основного монитора."""

    user32.MonitorFromPoint.argtypes = [
        wintypes.POINT,
        wintypes.DWORD,
    ]
    user32.MonitorFromPoint.restype = wintypes.HANDLE

    user32.GetMonitorInfoW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(MONITORINFO),
    ]
    user32.GetMonitorInfoW.restype = wintypes.BOOL

    # Получаем основной монитор.
    point = wintypes.POINT(0, 0)
    monitor_handle = user32.MonitorFromPoint(
        point,
        MONITOR_DEFAULTTOPRIMARY,
    )

    if not monitor_handle:
        raise ctypes.WinError(ctypes.get_last_error())

    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)

    if not user32.GetMonitorInfoW(
        monitor_handle,
        ctypes.byref(info),
    ):
        raise ctypes.WinError(ctypes.get_last_error())

    return Monitor(
        left=info.rcMonitor.left,
        top=info.rcMonitor.top,
        right=info.rcMonitor.right,
        bottom=info.rcMonitor.bottom,
        work_left=info.rcWork.left,
        work_top=info.rcWork.top,
        work_right=info.rcWork.right,
        work_bottom=info.rcWork.bottom,
        is_primary=bool(info.dwFlags & MONITORINFOF_PRIMARY),
    )


if __name__ == "__main__":
    monitor = get_primary_monitor()

    print("Primary monitor")
    print("------------------------------")
    print(f"Resolution: {monitor.width}x{monitor.height}")
    print(
        f"Bounds: ({monitor.left}, {monitor.top}) - ({monitor.right}, {monitor.bottom})"
    )
    print(
        f"Work area: "
        f"({monitor.work_left}, {monitor.work_top}) - "
        f"({monitor.work_right}, {monitor.work_bottom})"
    )
    print(f"Work size: {monitor.work_width}x{monitor.work_height}")
    print("------------------------------")
