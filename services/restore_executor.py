from typing import Any

from grid.models import DesktopGrid
from services.desktop_state_validator import DesktopStateValidator
from services.restore_models import (
    CurrentItemState,
    MoveSchedule,
    MoveStep,
    RestoreExecutionResult,
)


class RestoreExecutor:
    """Выполняет последовательность перемещений и откат."""

    def __init__(
        self,
        mover: Any,
        grid: DesktopGrid,
        validator: DesktopStateValidator | None = None,
    ) -> None:
        self._mover = mover
        self._grid = grid
        self._validator = validator

    def execute(
        self,
        schedule: MoveSchedule,
        current_items: list[CurrentItemState],
    ) -> RestoreExecutionResult:
        """Выполняет расписание восстановления."""

        # Проверяем расписание до начала перемещений.
        self._validate_schedule(schedule, current_items)

        attempted_steps: list[MoveStep] = []
        completed_steps = 0

        try:
            for step in schedule.steps:
                if self._validator is not None:
                    validation_errors = self._validator.validate_step(step)

                    if validation_errors:
                        raise RuntimeError(
                            f"Pre-move validation failed for {step.name!r}: "
                            + "; ".join(validation_errors)
                        )

                target_x, target_y = self._grid.to_coordinates(
                    step.to_column,
                    step.to_row,
                )

                attempted_steps.append(step)

                actual_x, actual_y = self._mover.move_to_screen(
                    index=step.index,
                    screen_x=target_x,
                    screen_y=target_y,
                )

                actual_cell = self._grid.to_cell(
                    actual_x,
                    actual_y,
                )

                expected_cell = (
                    step.to_column,
                    step.to_row,
                )

                if actual_cell != expected_cell:
                    raise RuntimeError(
                        f"Объект {step.name!r} оказался "
                        f"в ячейке {actual_cell}, "
                        f"ожидалась {expected_cell}"
                    )

                completed_steps += 1

        except Exception as error:
            rollback_errors = self._rollback(attempted_steps)

            return RestoreExecutionResult(
                success=False,
                completed_steps=completed_steps,
                rolled_back=bool(attempted_steps) and not rollback_errors,
                error=str(error),
                rollback_errors=tuple(rollback_errors),
            )

        return RestoreExecutionResult(
            success=True,
            completed_steps=completed_steps,
            rolled_back=False,
        )

    def _validate_schedule(
        self,
        schedule: MoveSchedule,
        current_items: list[CurrentItemState],
    ) -> None:
        """Проверяет корректность расписания до выполнения."""

        positions: dict[tuple[str, str], tuple[int, int]] = {}
        indices: dict[int, tuple[str, str]] = {}
        occupancy: dict[tuple[int, int], tuple[str, str]] = {}

        for item in current_items:
            key = self._identity_key(
                item.identity_type,
                item.parsing_name,
            )

            cell = (item.column, item.row)

            if key in positions:
                raise ValueError(f"Повторяющийся объект: {item.name!r}")

            if item.index in indices:
                raise ValueError(f"Повторяющийся индекс ListView: {item.index}")

            if cell in occupancy:
                raise ValueError(f"Несколько объектов занимают ячейку {cell}")

            positions[key] = cell
            indices[item.index] = key
            occupancy[cell] = key

        # Проверяем все шаги в памяти, не перемещая реальные иконки.
        for step in schedule.steps:
            key = self._identity_key(
                step.identity_type,
                step.parsing_name,
            )

            if key not in positions:
                raise ValueError(
                    f"Объект {step.name!r} отсутствует в текущем состоянии"
                )

            if indices.get(step.index) != key:
                raise ValueError(
                    f"Индекс {step.index} не соответствует объекту {step.name!r}"
                )

            current_cell = positions[key]

            expected_from = (
                step.from_column,
                step.from_row,
            )

            if current_cell != expected_from:
                raise ValueError(
                    f"Некорректная последовательность для "
                    f"{step.name!r}: ожидалось {current_cell}, "
                    f"получено {expected_from}"
                )

            target_cell = (
                step.to_column,
                step.to_row,
            )

            if not self._grid.is_valid_cell(*target_cell):
                raise ValueError(f"Целевая ячейка {target_cell} находится вне сетки")

            occupant = occupancy.get(target_cell)

            if occupant is not None and occupant != key:
                raise ValueError(f"Целевая ячейка {target_cell} занята другим объектом")

            del occupancy[current_cell]
            occupancy[target_cell] = key
            positions[key] = target_cell

    def _rollback(
        self,
        attempted_steps: list[MoveStep],
    ) -> list[str]:
        """Пытается отменить выполненные перемещения."""

        errors = []

        for step in reversed(attempted_steps):
            original_x, original_y = self._grid.to_coordinates(
                step.from_column,
                step.from_row,
            )

            try:
                actual_x, actual_y = self._mover.move_to_screen(
                    index=step.index,
                    screen_x=original_x,
                    screen_y=original_y,
                )

                actual_cell = self._grid.to_cell(
                    actual_x,
                    actual_y,
                )

                expected_cell = (
                    step.from_column,
                    step.from_row,
                )

                if actual_cell != expected_cell:
                    raise RuntimeError(
                        f"Ожидалась ячейка {expected_cell}, получена {actual_cell}"
                    )

            except Exception as error:
                errors.append(f"{step.name!r}: {error}")

        return errors

    @staticmethod
    def _identity_key(
        identity_type: str,
        parsing_name: str,
    ) -> tuple[str, str]:
        import ntpath

        if identity_type == "filesystem":
            normalized = ntpath.normcase(ntpath.normpath(parsing_name))
        else:
            normalized = parsing_name.casefold()

        return identity_type, normalized
