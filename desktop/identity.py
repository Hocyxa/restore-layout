import ctypes
import uuid
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

shell32 = ctypes.WinDLL("shell32", use_last_error=True)
ole32 = ctypes.WinDLL("ole32", use_last_error=True)
# COM initialization
COINIT_APARTMENTTHREADED = 0x2

ole32.CoInitializeEx.restype = ctypes.c_long
ole32.CoInitializeEx.argtypes = [
    ctypes.c_void_p,
    wintypes.DWORD,
]

ole32.CoUninitialize.restype = None
ole32.CoUninitialize.argtypes = []

# Known Folder identifiers
FOLDERID_DESKTOP = uuid.UUID("B4BFCC3A-DB2C-424C-B029-7FE99A87C641")

FOLDERID_PUBLIC_DESKTOP = uuid.UUID("C4AA340D-F20F-4863-AFEF-F87EF2E6BA25")

FOLDERID_RECYCLE_BIN = uuid.UUID("B7534046-3ECB-4C18-BE4E-64CD4CB7D6AC")


# SHGetFileInfo flags
SHGFI_PIDL = 0x00000008
SHGFI_DISPLAYNAME = 0x00000200

# SIGDN_DESKTOPABSOLUTEPARSING
SIGDN_DESKTOPABSOLUTEPARSING = 0x80028000


@contextmanager
def com_initialized() -> Iterator[None]:
    """Инициализирует COM на время выполнения блока."""

    result = ole32.CoInitializeEx(
        None,
        COINIT_APARTMENTTHREADED,
    )

    # HRESULT может быть отрицательным, поэтому проверяем
    # также специальный код RPC_E_CHANGED_MODE.
    unsigned_result = result & 0xFFFFFFFF

    # RPC_E_CHANGED_MODE: COM уже инициализирован
    # в другом apartment mode. Повторно инициализировать
    # и вызывать CoUninitialize в этом случае нельзя.
    if unsigned_result == 0x80010106:
        yield
        return

    if result < 0:
        raise OSError(f"CoInitializeEx failed: HRESULT=0x{unsigned_result:08X}")

    try:
        yield
    finally:
        ole32.CoUninitialize()


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_uuid(cls, value: uuid.UUID) -> "GUID":
        return cls.from_buffer_copy(value.bytes_le)


class SHFILEINFOW(ctypes.Structure):
    _fields_ = [
        ("hIcon", wintypes.HANDLE),
        ("iIcon", ctypes.c_int),
        ("dwAttributes", wintypes.DWORD),
        ("szDisplayName", wintypes.WCHAR * 260),
        ("szTypeName", wintypes.WCHAR * 80),
    ]


# SHGetKnownFolderPath
shell32.SHGetKnownFolderPath.restype = ctypes.c_long
shell32.SHGetKnownFolderPath.argtypes = [
    ctypes.POINTER(GUID),
    wintypes.DWORD,
    wintypes.HANDLE,
    ctypes.POINTER(ctypes.c_void_p),
]

# SHGetKnownFolderIDList
shell32.SHGetKnownFolderIDList.restype = ctypes.c_long
shell32.SHGetKnownFolderIDList.argtypes = [
    ctypes.POINTER(GUID),
    wintypes.DWORD,
    wintypes.HANDLE,
    ctypes.POINTER(ctypes.c_void_p),
]

# SHGetFileInfoW
shell32.SHGetFileInfoW.restype = ctypes.c_size_t
shell32.SHGetFileInfoW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.POINTER(SHFILEINFOW),
    wintypes.UINT,
    wintypes.UINT,
]

# SHGetNameFromIDList
shell32.SHGetNameFromIDList.restype = ctypes.c_long
shell32.SHGetNameFromIDList.argtypes = [
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.POINTER(ctypes.c_void_p),
]

# CoTaskMemFree
ole32.CoTaskMemFree.restype = None
ole32.CoTaskMemFree.argtypes = [
    ctypes.c_void_p,
]


@dataclass(frozen=True, slots=True)
class IdentityCandidate:
    kind: Literal["filesystem", "shell"]
    parsing_name: str
    source: str
    path: str | None = None


@dataclass(frozen=True, slots=True)
class IdentityResolution:
    status: Literal["matched", "ambiguous", "unresolved"]
    candidates: tuple[IdentityCandidate, ...]

    @property
    def identity(self) -> IdentityCandidate | None:
        if self.status != "matched":
            return None

        return self.candidates[0]


def _get_known_folder_path(folder_id: uuid.UUID) -> Path:
    """Получает путь системной Known Folder."""

    guid = GUID.from_uuid(folder_id)
    result_path = ctypes.c_void_p()

    result = shell32.SHGetKnownFolderPath(
        ctypes.byref(guid),
        0,
        None,
        ctypes.byref(result_path),
    )

    if result < 0:
        raise OSError(
            f"SHGetKnownFolderPath failed: HRESULT=0x{result & 0xFFFFFFFF:08X}"
        )

    address = result_path.value

    if address is None:
        raise RuntimeError("SHGetKnownFolderPath вернул NULL")

    try:
        return Path(ctypes.wstring_at(address))
    finally:
        ole32.CoTaskMemFree(result_path)


def _get_shell_display_name(path: Path) -> str:
    """Получает отображаемое имя объекта через Windows Shell."""

    info = SHFILEINFOW()

    result = shell32.SHGetFileInfoW(
        str(path),
        0,
        ctypes.byref(info),
        ctypes.sizeof(info),
        SHGFI_DISPLAYNAME,
    )

    if not result:
        raise OSError(f"SHGetFileInfoW failed for: {path}")

    return info.szDisplayName


def _get_shell_parsing_name(pidl: ctypes.c_void_p) -> str:
    """Получает абсолютное Parsing Name Shell-объекта."""

    result_name = ctypes.c_void_p()

    result = shell32.SHGetNameFromIDList(
        pidl,
        SIGDN_DESKTOPABSOLUTEPARSING,
        ctypes.byref(result_name),
    )

    if result < 0:
        raise OSError(
            f"SHGetNameFromIDList failed: HRESULT=0x{result & 0xFFFFFFFF:08X}"
        )

    address = result_name.value

    if address is None:
        raise RuntimeError("SHGetNameFromIDList вернул NULL")

    try:
        return ctypes.wstring_at(address)
    finally:
        ole32.CoTaskMemFree(result_name)


def _get_shell_folder_identity(
    folder_id: uuid.UUID,
) -> tuple[str, str]:
    """Получает отображаемое имя и Parsing Name Shell-папки."""

    guid = GUID.from_uuid(folder_id)
    pidl = ctypes.c_void_p()

    result = shell32.SHGetKnownFolderIDList(
        ctypes.byref(guid),
        0,
        None,
        ctypes.byref(pidl),
    )

    if result < 0:
        raise OSError(
            f"SHGetKnownFolderIDList failed: HRESULT=0x{result & 0xFFFFFFFF:08X}"
        )

    try:
        info = SHFILEINFOW()

        result = shell32.SHGetFileInfoW(
            ctypes.cast(pidl, wintypes.LPCWSTR),
            0,
            ctypes.byref(info),
            ctypes.sizeof(info),
            SHGFI_PIDL | SHGFI_DISPLAYNAME,
        )

        if not result:
            raise OSError("SHGetFileInfoW failed for Shell PIDL")

        display_name = info.szDisplayName
        parsing_name = _get_shell_parsing_name(pidl)

        return display_name, parsing_name

    finally:
        ole32.CoTaskMemFree(pidl)


class DesktopIdentityResolver:
    """Сопоставляет отображаемые имена с объектами Windows."""

    def __init__(self) -> None:
        self._entries: dict[
            str,
            list[IdentityCandidate],
        ] = defaultdict(list)

        self._scan_filesystem()
        self._scan_shell_objects()

    def _add_candidate(
        self,
        display_name: str,
        candidate: IdentityCandidate,
    ) -> None:
        key = display_name.casefold()

        existing = self._entries[key]

        if any(
            item.parsing_name.casefold() == candidate.parsing_name.casefold()
            for item in existing
        ):
            return

        existing.append(candidate)

    def _scan_filesystem(self) -> None:
        """Сканирует пользовательский и общедоступный Desktop."""

        folders = [
            (
                _get_known_folder_path(FOLDERID_DESKTOP),
                "User Desktop",
            ),
            (
                _get_known_folder_path(FOLDERID_PUBLIC_DESKTOP),
                "Public Desktop",
            ),
        ]

        for folder, source in folders:
            if not folder.exists():
                continue

            for path in folder.iterdir():
                display_name = _get_shell_display_name(path)

                self._add_candidate(
                    display_name,
                    IdentityCandidate(
                        kind="filesystem",
                        parsing_name=str(path),
                        source=source,
                        path=str(path),
                    ),
                )

    def _scan_shell_objects(self) -> None:
        """Регистрирует известные системные Shell-объекты."""

        display_name, parsing_name = _get_shell_folder_identity(FOLDERID_RECYCLE_BIN)

        self._add_candidate(
            display_name,
            IdentityCandidate(
                kind="shell",
                parsing_name=parsing_name,
                source="Windows Shell",
            ),
        )

    def resolve(self, display_name: str) -> IdentityResolution:
        """Находит объект по отображаемому имени."""

        candidates = tuple(self._entries.get(display_name.casefold(), []))

        if len(candidates) == 1:
            return IdentityResolution(
                status="matched",
                candidates=candidates,
            )

        if len(candidates) > 1:
            return IdentityResolution(
                status="ambiguous",
                candidates=candidates,
            )

        return IdentityResolution(
            status="unresolved",
            candidates=(),
        )

    def resolve_all(
        self,
        display_names: list[str],
    ) -> list[IdentityResolution]:
        return [self.resolve(name) for name in display_names]
