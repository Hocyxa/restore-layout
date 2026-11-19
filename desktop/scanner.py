from dataclasses import dataclass

from desktop.monitor import Monitor
from desktop.winapi import (
    find_list_view,
    get_client_origin_on_screen,
    get_item_count,
    get_item_position,
    get_item_text,
)


@dataclass(frozen=True, slots=True)
class DesktopItem:
    index: int
    name: str

    client_x: int
    client_y: int

    screen_x: int
    screen_y: int

    on_primary_monitor: bool
    inside_work_area: bool


class DesktopScanner:
    def __init__(self, monitor: Monitor) -> None:
        self._monitor = monitor

    def scan(self) -> list[DesktopItem]:
        """Сканирует элементы рабочего стола."""

        hwnd = find_list_view()

        origin_x, origin_y = get_client_origin_on_screen(hwnd)
        item_count = get_item_count(hwnd)

        items: list[DesktopItem] = []

        for index in range(item_count):
            name = get_item_text(hwnd, index)

            client_x, client_y = get_item_position(
                hwnd,
                index,
            )

            screen_x = origin_x + client_x
            screen_y = origin_y + client_y

            on_primary_monitor = (
                self._monitor.left <= screen_x < self._monitor.right
                and self._monitor.top <= screen_y < self._monitor.bottom
            )

            inside_work_area = (
                self._monitor.work_left <= screen_x < self._monitor.work_right
                and self._monitor.work_top <= screen_y < self._monitor.work_bottom
            )

            items.append(
                DesktopItem(
                    index=index,
                    name=name,
                    client_x=client_x,
                    client_y=client_y,
                    screen_x=screen_x,
                    screen_y=screen_y,
                    on_primary_monitor=on_primary_monitor,
                    inside_work_area=inside_work_area,
                )
            )

        return items
