import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# ListView messages
LVM_FIRST = 0x1000
LVM_GETITEMCOUNT = LVM_FIRST + 4
LVM_GETITEMPOSITION = LVM_FIRST + 16
LVM_GETITEMSPACING = LVM_FIRST + 51
LVM_GETITEMTEXTW = LVM_FIRST + 115

PROCESS_VM_WRITE = 0x0020
# Process access rights
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400

# Memory allocation
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04

LVM_SETITEMPOSITION32 = LVM_FIRST + 49


def set_item_position(
    hwnd: int,
    index: int,
    x: int,
    y: int,
) -> None:
    """Устанавливает позицию элемента SysListView32."""

    process_id = ctypes.c_ulong()

    thread_id = user32.GetWindowThreadProcessId(
        hwnd,
        ctypes.byref(process_id),
    )

    if not thread_id:
        raise ctypes.WinError(ctypes.get_last_error())

    process_handle = kernel32.OpenProcess(
        PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_QUERY_INFORMATION,
        False,
        process_id.value,
    )

    if not process_handle:
        raise ctypes.WinError(ctypes.get_last_error())

    remote_memory = None

    try:
        point = POINT(x, y)
        point_size = ctypes.sizeof(POINT)

        remote_memory = kernel32.VirtualAllocEx(
            process_handle,
            None,
            point_size,
            MEM_COMMIT | MEM_RESERVE,
            PAGE_READWRITE,
        )

        if not remote_memory:
            raise ctypes.WinError(ctypes.get_last_error())

        bytes_written = ctypes.c_size_t()

        success = kernel32.WriteProcessMemory(
            process_handle,
            remote_memory,
            ctypes.byref(point),
            point_size,
            ctypes.byref(bytes_written),
        )

        if not success:
            raise ctypes.WinError(ctypes.get_last_error())

        if bytes_written.value != point_size:
            raise OSError(
                "Не удалось полностью записать POINT в память процесса Explorer"
            )

        result = user32.SendMessageW(
            hwnd,
            LVM_SETITEMPOSITION32,
            index,
            remote_memory,
        )

        if not result:
            raise OSError(
                f"LVM_SETITEMPOSITION32 завершился ошибкой "
                f"для элемента с индексом {index}"
            )

    finally:
        if remote_memory:
            kernel32.VirtualFreeEx(
                process_handle,
                remote_memory,
                0,
                MEM_RELEASE,
            )

        kernel32.CloseHandle(process_handle)


class LVITEMW(ctypes.Structure):
    """Структура элемента Windows ListView."""

    _fields_ = [
        ("mask", wintypes.UINT),
        ("iItem", ctypes.c_int),
        ("iSubItem", ctypes.c_int),
        ("state", wintypes.UINT),
        ("stateMask", wintypes.UINT),
        ("pszText", ctypes.c_void_p),
        ("cchTextMax", ctypes.c_int),
        ("iImage", ctypes.c_int),
        ("lParam", ctypes.c_ssize_t),
        ("iIndent", ctypes.c_int),
        ("iGroupId", ctypes.c_int),
        ("cColumns", wintypes.UINT),
        ("puColumns", ctypes.c_void_p),
        ("piColFmt", ctypes.c_void_p),
        ("iGroup", ctypes.c_int),
    ]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class POINT(ctypes.Structure):
    _fields_ = [
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
    ]


# FindWindowW
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
]

# FindWindowExW
user32.FindWindowExW.restype = wintypes.HWND
user32.FindWindowExW.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
]

# SendMessageW
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.SendMessageW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    ctypes.c_size_t,
    ctypes.c_ssize_t,
]

# GetClientRect
user32.GetClientRect.restype = wintypes.BOOL
user32.GetClientRect.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(RECT),
]

# ClientToScreen
user32.ClientToScreen.restype = wintypes.BOOL
user32.ClientToScreen.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(POINT),
]

# GetWindowThreadProcessId
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(wintypes.DWORD),
]

# OpenProcess
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [
    wintypes.DWORD,
    wintypes.BOOL,
    wintypes.DWORD,
]

# CloseHandle
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [
    wintypes.HANDLE,
]

# VirtualAllocEx
kernel32.VirtualAllocEx.restype = ctypes.c_void_p
kernel32.VirtualAllocEx.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_size_t,
    wintypes.DWORD,
    wintypes.DWORD,
]

# VirtualFreeEx
kernel32.VirtualFreeEx.restype = wintypes.BOOL
kernel32.VirtualFreeEx.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_size_t,
    wintypes.DWORD,
]

# ReadProcessMemory
kernel32.ReadProcessMemory.restype = wintypes.BOOL
kernel32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.WriteProcessMemory.restype = wintypes.BOOL
kernel32.WriteProcessMemory.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]


def get_item_text(
    hwnd: int,
    index: int,
    buffer_size: int = 512,
) -> str:
    """Получает текст элемента ListView."""

    item_count = get_item_count(hwnd)

    if not 0 <= index < item_count:
        raise IndexError(f"Индекс элемента {index} вне диапазона")

    if buffer_size <= 1:
        raise ValueError("Размер буфера должен быть больше 1")

    process_id = wintypes.DWORD()

    thread_id = user32.GetWindowThreadProcessId(
        hwnd,
        ctypes.byref(process_id),
    )

    if not thread_id or not process_id.value:
        raise ctypes.WinError(ctypes.get_last_error())

    access = (
        PROCESS_VM_OPERATION
        | PROCESS_VM_READ
        | PROCESS_VM_WRITE
        | PROCESS_QUERY_INFORMATION
    )

    process_handle = kernel32.OpenProcess(
        access,
        False,
        process_id.value,
    )

    if not process_handle:
        raise ctypes.WinError(ctypes.get_last_error())

    remote_address = None

    try:
        structure_size = ctypes.sizeof(LVITEMW)
        text_size = buffer_size * ctypes.sizeof(ctypes.c_wchar)
        total_size = structure_size + text_size

        remote_address = kernel32.VirtualAllocEx(
            process_handle,
            None,
            total_size,
            MEM_COMMIT | MEM_RESERVE,
            PAGE_READWRITE,
        )

        if not remote_address:
            raise ctypes.WinError(ctypes.get_last_error())

        remote_base = int(remote_address)
        remote_text_address = remote_base + structure_size

        item = LVITEMW()
        item.iSubItem = 0
        item.pszText = remote_text_address
        item.cchTextMax = buffer_size

        # Записываем LVITEMW в память Explorer.
        bytes_written = ctypes.c_size_t()

        write_result = kernel32.WriteProcessMemory(
            process_handle,
            ctypes.c_void_p(remote_base),
            ctypes.byref(item),
            structure_size,
            ctypes.byref(bytes_written),
        )

        if not write_result:
            raise ctypes.WinError(ctypes.get_last_error())

        if bytes_written.value != structure_size:
            raise RuntimeError("Не удалось полностью записать LVITEMW")

        # Запрашиваем текст элемента.
        result = user32.SendMessageW(
            hwnd,
            LVM_GETITEMTEXTW,
            index,
            ctypes.c_ssize_t(remote_base).value,
        )

        if result < 0:
            raise RuntimeError(f"LVM_GETITEMTEXTW завершился ошибкой: {result}")

        # Читаем текст из памяти Explorer.
        text_buffer = ctypes.create_unicode_buffer(buffer_size)
        bytes_read = ctypes.c_size_t()

        read_result = kernel32.ReadProcessMemory(
            process_handle,
            ctypes.c_void_p(remote_text_address),
            ctypes.byref(text_buffer),
            text_size,
            ctypes.byref(bytes_read),
        )

        if not read_result:
            raise ctypes.WinError(ctypes.get_last_error())

        if bytes_read.value != text_size:
            raise RuntimeError("Не удалось полностью прочитать текст элемента")

        if result >= buffer_size - 1:
            raise RuntimeError(
                f"Текст элемента {index} может быть обрезан. Увеличь buffer_size."
            )

        return text_buffer.value

    finally:
        if remote_address:
            kernel32.VirtualFreeEx(
                process_handle,
                remote_address,
                0,
                MEM_RELEASE,
            )

        kernel32.CloseHandle(process_handle)


def find_list_view() -> int:
    """Находит SysListView32 рабочего стола."""

    def find_def_view(parent: int) -> int:
        return int(
            user32.FindWindowExW(
                parent,
                None,
                "SHELLDLL_DefView",
                None,
            )
            or 0
        )

    def find_list_view_in(parent: int) -> int:
        return int(
            user32.FindWindowExW(
                parent,
                None,
                "SysListView32",
                None,
            )
            or 0
        )

    progman = int(user32.FindWindowW("Progman", None) or 0)

    if progman:
        def_view = find_def_view(progman)

        if def_view:
            list_view = find_list_view_in(def_view)

            if list_view:
                return list_view

    raise RuntimeError("Не удалось найти SysListView32 рабочего стола")


def get_item_spacing(hwnd: int) -> tuple[int, int]:
    """Возвращает шаг сетки ListView."""

    result = user32.SendMessageW(
        hwnd,
        LVM_GETITEMSPACING,
        0,
        0,
    )

    step_x = result & 0xFFFF
    step_y = (result >> 16) & 0xFFFF

    if step_x <= 0 or step_y <= 0:
        raise RuntimeError("Не удалось определить шаг сетки")

    return step_x, step_y


def get_client_size(hwnd: int) -> tuple[int, int]:
    """Получает размеры клиентской области ListView."""

    rect = RECT()

    if not user32.GetClientRect(
        hwnd,
        ctypes.byref(rect),
    ):
        raise ctypes.WinError(ctypes.get_last_error())

    return (
        rect.right - rect.left,
        rect.bottom - rect.top,
    )


def get_client_origin_on_screen(hwnd: int) -> tuple[int, int]:
    """Получает экранные координаты начала клиентской области."""

    point = POINT(0, 0)

    if not user32.ClientToScreen(
        hwnd,
        ctypes.byref(point),
    ):
        raise ctypes.WinError(ctypes.get_last_error())

    return point.x, point.y


def get_item_count(hwnd: int) -> int:
    """Возвращает количество элементов ListView."""

    return int(
        user32.SendMessageW(
            hwnd,
            LVM_GETITEMCOUNT,
            0,
            0,
        )
    )


def get_item_position(
    hwnd: int,
    index: int,
) -> tuple[int, int]:
    """Получает координаты элемента ListView.

    Координаты возвращаются относительно клиентской области ListView.
    """

    item_count = get_item_count(hwnd)

    if not 0 <= index < item_count:
        raise IndexError(f"Индекс элемента {index} вне диапазона 0..{item_count - 1}")

    # Получаем PID процесса, которому принадлежит ListView.
    process_id = wintypes.DWORD()

    thread_id = user32.GetWindowThreadProcessId(
        hwnd,
        ctypes.byref(process_id),
    )

    if not thread_id or not process_id.value:
        raise ctypes.WinError(ctypes.get_last_error())

    access = PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_QUERY_INFORMATION

    process_handle = kernel32.OpenProcess(
        access,
        False,
        process_id.value,
    )

    if not process_handle:
        raise ctypes.WinError(ctypes.get_last_error())

    remote_address = None

    try:
        point_size = ctypes.sizeof(POINT)

        # Выделяем память в адресном пространстве Explorer.
        remote_address = kernel32.VirtualAllocEx(
            process_handle,
            None,
            point_size,
            MEM_COMMIT | MEM_RESERVE,
            PAGE_READWRITE,
        )

        if not remote_address:
            raise ctypes.WinError(ctypes.get_last_error())

        # LVM_GETITEMPOSITION ожидает указатель на POINT
        # именно в адресном пространстве процесса ListView.
        result = user32.SendMessageW(
            hwnd,
            LVM_GETITEMPOSITION,
            index,
            ctypes.c_ssize_t(remote_address).value,
        )

        if not result:
            raise RuntimeError(
                f"LVM_GETITEMPOSITION завершился ошибкой для элемента {index}"
            )

        # Читаем POINT из памяти Explorer в память нашего процесса.
        point = POINT()
        bytes_read = ctypes.c_size_t()

        read_result = kernel32.ReadProcessMemory(
            process_handle,
            remote_address,
            ctypes.byref(point),
            point_size,
            ctypes.byref(bytes_read),
        )

        if not read_result:
            raise ctypes.WinError(ctypes.get_last_error())

        if bytes_read.value != point_size:
            raise RuntimeError(f"Прочитано {bytes_read.value} байт вместо {point_size}")

        return point.x, point.y

    finally:
        if remote_address:
            kernel32.VirtualFreeEx(
                process_handle,
                remote_address,
                0,
                MEM_RELEASE,
            )

        kernel32.CloseHandle(process_handle)
