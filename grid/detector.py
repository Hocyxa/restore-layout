from collections import Counter
from math import ceil

from desktop.monitor import Monitor
from desktop.scanner import DesktopScanner
from desktop.winapi import find_list_view, get_item_spacing
from grid.models import DesktopGrid


class DesktopGridDetector:
    TOLERANCE = 2

    def __init__(self, monitor: Monitor) -> None:
        self._monitor = monitor
        self._scanner = DesktopScanner(monitor)

    def detect(self) -> DesktopGrid:
        hwnd = find_list_view()
        step_x, step_y = get_item_spacing(hwnd)

        if step_x <= 0 or step_y <= 0:
            raise ValueError(f"Некорректный шаг сетки: {step_x}x{step_y}")

        items = [item for item in self._scanner.scan() if item.on_primary_monitor]

        if not items:
            raise RuntimeError(
                "Не удалось определить сетку: на основном мониторе нет значков"
            )

        # Вычисляем фазу сетки относительно начала монитора.
        x_offsets = [(item.screen_x - self._monitor.left) % step_x for item in items]
        y_offsets = [(item.screen_y - self._monitor.top) % step_y for item in items]

        phase_x = self._get_dominant_offset(x_offsets)
        phase_y = self._get_dominant_offset(y_offsets)

        # Переводим фазу в абсолютные координаты экрана.
        phase_x += self._monitor.left
        phase_y += self._monitor.top

        # Проверяем, что координаты всех значков соответствуют
        # обнаруженной сетке.
        self._validate_alignment(
            items=items,
            phase_x=phase_x,
            phase_y=phase_y,
            step_x=step_x,
            step_y=step_y,
        )

        # Находим первую ячейку, попадающую в рабочую область.
        origin_x = self._get_first_grid_coordinate(
            phase=phase_x,
            step=step_x,
            lower_bound=self._monitor.work_left,
        )
        origin_y = self._get_first_grid_coordinate(
            phase=phase_y,
            step=step_y,
            lower_bound=self._monitor.work_top,
        )

        columns = ((self._monitor.work_right - 1 - origin_x) // step_x) + 1

        rows = ((self._monitor.work_bottom - 1 - origin_y) // step_y) + 1

        if columns <= 0 or rows <= 0:
            raise RuntimeError("Не удалось определить допустимые размеры сетки")

        grid = DesktopGrid(
            origin_x=origin_x,
            origin_y=origin_y,
            step_x=step_x,
            step_y=step_y,
            columns=columns,
            rows=rows,
        )

        # Проверяем, что каждый значок попадает в допустимую ячейку.
        for item in items:
            try:
                grid.to_cell(item.screen_x, item.screen_y)
            except ValueError as error:
                raise RuntimeError(
                    f"Значок {item.name!r} "
                    f"не соответствует обнаруженной сетке: "
                    f"({item.screen_x}, {item.screen_y})"
                ) from error

        return grid

    @staticmethod
    def _get_dominant_offset(offsets: list[int]) -> int:
        """
        Возвращает наиболее часто встречающийся остаток
        координат от деления на шаг сетки.
        """
        counts = Counter(offsets)

        max_count = max(counts.values())

        most_common = [offset for offset, count in counts.items() if count == max_count]

        if len(most_common) != 1:
            raise RuntimeError(
                "Не удалось однозначно определить фазу сетки: "
                f"обнаружены варианты {most_common}"
            )

        return most_common[0]

    def _validate_alignment(
        self,
        items,
        phase_x: int,
        phase_y: int,
        step_x: int,
        step_y: int,
    ) -> None:
        """
        Проверяет, что координаты всех значков соответствуют
        одной и той же сетке с допустимой погрешностью.
        """
        for item in items:
            relative_x = item.screen_x - phase_x
            relative_y = item.screen_y - phase_y

            deviation_x = min(
                relative_x % step_x,
                (-relative_x) % step_x,
            )
            deviation_y = min(
                relative_y % step_y,
                (-relative_y) % step_y,
            )

            if deviation_x > self.TOLERANCE or deviation_y > self.TOLERANCE:
                raise RuntimeError(
                    f"Значок {item.name!r} не соответствует сетке. "
                    f"Координаты: ({item.screen_x}, {item.screen_y}), "
                    f"отклонение: ({deviation_x}, {deviation_y})"
                )

    @staticmethod
    def _get_first_grid_coordinate(
        phase: int,
        step: int,
        lower_bound: int,
    ) -> int:
        """
        Находит первую координату сетки, не выходящую
        за левую или верхнюю границу рабочей области.
        """
        offset = ceil((lower_bound - phase) / step)
        return phase + offset * step
