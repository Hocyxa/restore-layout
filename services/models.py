from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True, slots=True)
class MonitorSnapshot:
    """Характеристики монитора на момент сохранения."""

    left: int
    top: int
    right: int
    bottom: int

    work_left: int
    work_top: int
    work_right: int
    work_bottom: int

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


@dataclass(frozen=True, slots=True)
class GridSnapshot:
    """Параметры сетки рабочего стола."""

    origin_x: int
    origin_y: int
    step_x: int
    step_y: int
    columns: int
    rows: int


@dataclass(frozen=True, slots=True)
class ItemIdentitySnapshot:
    """Идентификатор объекта рабочего стола."""

    type: Literal["filesystem", "shell"]
    parsing_name: str


@dataclass(frozen=True, slots=True)
class ItemPositionSnapshot:
    """Положение объекта в сетке."""

    column: int
    row: int


@dataclass(frozen=True, slots=True)
class DesktopItemSnapshot:
    """Сохранённое состояние отдельного объекта."""

    name: str
    identity: ItemIdentitySnapshot
    position: ItemPositionSnapshot


@dataclass(frozen=True, slots=True)
class DesktopSnapshot:
    """Полный снимок рабочего стола."""

    version: int
    created_at: datetime
    monitor: MonitorSnapshot
    grid: GridSnapshot
    items: tuple[DesktopItemSnapshot, ...]
