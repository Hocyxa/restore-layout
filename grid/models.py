from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DesktopGrid:
    origin_x: int
    origin_y: int

    step_x: int
    step_y: int

    columns: int
    rows: int

    @property
    def total_cells(self) -> int:
        return self.columns * self.rows

    def to_cell(self, x: int, y: int) -> tuple[int, int]:
        """Преобразует экранные координаты в индексы ячейки."""

        column_offset = x - self.origin_x
        row_offset = y - self.origin_y

        column = round(column_offset / self.step_x)
        row = round(row_offset / self.step_y)

        expected_x = self.origin_x + column * self.step_x
        expected_y = self.origin_y + row * self.step_y

        if abs(x - expected_x) > 2 or abs(y - expected_y) > 2:
            raise ValueError(f"Координаты ({x}, {y}) не соответствуют сетке")

        if not self.is_valid_cell(column, row):
            raise ValueError(f"Ячейка ({column}, {row}) находится за пределами сетки")

        return column, row

    def to_coordinates(
        self,
        column: int,
        row: int,
    ) -> tuple[int, int]:
        """Преобразует индексы ячейки в экранные координаты."""

        if not self.is_valid_cell(column, row):
            raise ValueError(f"Ячейка ({column}, {row}) находится за пределами сетки")

        x = self.origin_x + column * self.step_x
        y = self.origin_y + row * self.step_y

        return x, y

    def is_valid_cell(self, column: int, row: int) -> bool:
        return 0 <= column < self.columns and 0 <= row < self.rows
