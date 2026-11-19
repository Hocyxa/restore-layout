from dataclasses import dataclass
from typing import Literal

IdentityType = Literal["filesystem", "shell"]


@dataclass(frozen=True, slots=True)
class CurrentItemState:
    """Состояние объекта на текущем рабочем столе."""

    index: int
    name: str
    identity_type: IdentityType
    parsing_name: str
    column: int
    row: int


@dataclass(frozen=True, slots=True)
class RestoreAction:
    """Действие по восстановлению положения объекта."""

    index: int
    name: str
    identity_type: IdentityType
    parsing_name: str

    current_column: int
    current_row: int

    target_column: int
    target_row: int


@dataclass(frozen=True, slots=True)
class ItemReference:
    """Ссылка на объект для диагностических сообщений."""

    name: str
    identity_type: IdentityType
    parsing_name: str


@dataclass(frozen=True, slots=True)
class RestorePlan:
    """Результат анализа возможности восстановления."""

    actions: tuple[RestoreAction, ...]
    missing_items: tuple[ItemReference, ...]
    unexpected_items: tuple[ItemReference, ...]

    conflicts: tuple[str, ...]
    compatibility_errors: tuple[str, ...]
    identity_errors: tuple[str, ...]

    @property
    def is_safe(self) -> bool:
        return (
            not self.conflicts
            and not self.compatibility_errors
            and not self.identity_errors
        )


@dataclass(frozen=True, slots=True)
class MoveStep:
    """Одно перемещение объекта."""

    index: int
    name: str
    identity_type: IdentityType
    parsing_name: str

    from_column: int
    from_row: int

    to_column: int
    to_row: int

    is_temporary: bool = False


@dataclass(frozen=True, slots=True)
class MoveSchedule:
    """Последовательность перемещений для восстановления."""

    steps: tuple[MoveStep, ...]
    temporary_moves: int


@dataclass(frozen=True, slots=True)
class RestoreExecutionResult:
    """Результат выполнения последовательности восстановления."""

    success: bool
    completed_steps: int
    rolled_back: bool
    error: str | None = None
    rollback_errors: tuple[str, ...] = ()
