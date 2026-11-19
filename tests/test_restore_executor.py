from dataclasses import replace

import pytest

from desktop.mover import DesktopMover
from grid.models import DesktopGrid
from services.restore_executor import RestoreExecutor
from services.restore_models import (
    CurrentItemState,
    MoveSchedule,
    MoveStep,
)


class FakeMover(DesktopMover):
    """Имитация DesktopMover без обращения к WinAPI."""

    def __init__(self, fail_on_call: int | None = None) -> None:
        self.calls = []
        self.fail_on_call = fail_on_call

    def move_to_screen(
        self,
        index: int,
        screen_x: int,
        screen_y: int,
    ) -> tuple[int, int]:
        self.calls.append((index, screen_x, screen_y))

        if len(self.calls) == self.fail_on_call:
            raise RuntimeError("Simulated movement error")

        return screen_x, screen_y


@pytest.fixture
def grid() -> DesktopGrid:
    return DesktopGrid(
        origin_x=22,
        origin_y=2,
        step_x=76,
        step_y=84,
        columns=25,
        rows=13,
    )


@pytest.fixture
def current_items() -> list[CurrentItemState]:
    return [
        CurrentItemState(
            index=5,
            name="Works",
            identity_type="filesystem",
            parsing_name=r"C:\Users\User\Desktop\Works",
            column=24,
            row=4,
        ),
        CurrentItemState(
            index=27,
            name="notes_ept.md",
            identity_type="filesystem",
            parsing_name=r"C:\Users\User\Desktop\notes_ept.md",
            column=24,
            row=2,
        ),
    ]


@pytest.fixture
def swap_schedule() -> MoveSchedule:
    return MoveSchedule(
        steps=(
            MoveStep(
                index=5,
                name="Works",
                identity_type="filesystem",
                parsing_name=r"C:\Users\User\Desktop\Works",
                from_column=24,
                from_row=4,
                to_column=1,
                to_row=0,
                is_temporary=True,
            ),
            MoveStep(
                index=27,
                name="notes_ept.md",
                identity_type="filesystem",
                parsing_name=r"C:\Users\User\Desktop\notes_ept.md",
                from_column=24,
                from_row=2,
                to_column=24,
                to_row=4,
            ),
            MoveStep(
                index=5,
                name="Works",
                identity_type="filesystem",
                parsing_name=r"C:\Users\User\Desktop\Works",
                from_column=1,
                from_row=0,
                to_column=24,
                to_row=2,
            ),
        ),
        temporary_moves=1,
    )


def test_empty_schedule(grid, current_items):
    mover = FakeMover()
    executor = RestoreExecutor(mover, grid)

    schedule = MoveSchedule(
        steps=(),
        temporary_moves=0,
    )

    result = executor.execute(schedule, current_items)

    assert result.success is True
    assert result.completed_steps == 0
    assert result.rolled_back is False
    assert mover.calls == []


def test_successful_execution(
    grid,
    current_items,
    swap_schedule,
):
    mover = FakeMover()
    executor = RestoreExecutor(mover, grid)

    result = executor.execute(
        swap_schedule,
        current_items,
    )

    assert result.success is True
    assert result.completed_steps == 3
    assert result.rolled_back is False
    assert len(mover.calls) == 3


def test_invalid_index_prevents_execution(
    grid,
    current_items,
    swap_schedule,
):
    mover = FakeMover()
    executor = RestoreExecutor(mover, grid)

    invalid_step = replace(
        swap_schedule.steps[0],
        index=999,
    )

    invalid_schedule = MoveSchedule(
        steps=(
            invalid_step,
            *swap_schedule.steps[1:],
        ),
        temporary_moves=swap_schedule.temporary_moves,
    )

    with pytest.raises(ValueError):
        executor.execute(invalid_schedule, current_items)

    assert mover.calls == []


def test_failure_triggers_rollback(
    grid,
    current_items,
    swap_schedule,
):
    mover = FakeMover(fail_on_call=2)
    executor = RestoreExecutor(mover, grid)

    result = executor.execute(
        swap_schedule,
        current_items,
    )

    assert result.success is False
    assert result.completed_steps == 1
    assert result.rolled_back is True
    assert result.error is not None
    assert len(result.rollback_errors) == 0

    # Два вызова выполнения и два вызова отката.
    assert len(mover.calls) == 4


def test_target_outside_grid_prevents_execution(
    grid,
    current_items,
    swap_schedule,
):
    mover = FakeMover()
    executor = RestoreExecutor(mover, grid)

    invalid_step = replace(
        swap_schedule.steps[0],
        to_column=100,
    )

    invalid_schedule = MoveSchedule(
        steps=(
            invalid_step,
            *swap_schedule.steps[1:],
        ),
        temporary_moves=swap_schedule.temporary_moves,
    )

    with pytest.raises(ValueError):
        executor.execute(invalid_schedule, current_items)

    assert mover.calls == []
