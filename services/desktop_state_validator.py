import ntpath

from desktop.identity import (
    DesktopIdentityResolver,
    com_initialized,
)
from desktop.scanner import DesktopScanner
from grid.models import DesktopGrid
from services.restore_models import CurrentItemState, MoveStep


class DesktopStateValidator:
    """Проверяет актуальность состояния рабочего стола."""

    def __init__(
        self,
        scanner: DesktopScanner,
        resolver: DesktopIdentityResolver,
        grid: DesktopGrid,
    ) -> None:
        self._scanner = scanner
        self._resolver = resolver
        self._grid = grid

    def validate(
        self,
        expected_items: list[CurrentItemState],
    ) -> tuple[str, ...]:
        """
        Сравнивает текущее состояние рабочего стола
        с состоянием, на основе которого строилось расписание.

        Возвращает список обнаруженных расхождений.
        Пустой кортеж означает, что состояние совпадает.
        """

        errors: list[str] = []
        actual_items: list[CurrentItemState] = []

        with com_initialized():
            desktop_items = self._scanner.scan()

            for item in desktop_items:
                if not item.on_primary_monitor:
                    continue

                if not item.inside_work_area:
                    continue

                resolution = self._resolver.resolve(item.name)

                if resolution.status != "matched":
                    errors.append(
                        f"{item.name}: identity status is {resolution.status}"
                    )
                    continue

                identity = resolution.identity

                if identity is None:
                    errors.append(f"{item.name}: identity is None")
                    continue

                try:
                    column, row = self._grid.to_cell(
                        item.screen_x,
                        item.screen_y,
                    )
                except ValueError as error:
                    errors.append(f"{item.name}: cannot determine grid cell: {error}")
                    continue

                actual_items.append(
                    CurrentItemState(
                        index=item.index,
                        name=item.name,
                        identity_type=identity.kind,
                        parsing_name=identity.parsing_name,
                        column=column,
                        row=row,
                    )
                )

        if len(expected_items) != len(actual_items):
            errors.append(
                "Desktop item count changed: "
                f"expected {len(expected_items)}, "
                f"actual {len(actual_items)}"
            )

        expected_by_identity = self._index_items(
            expected_items,
            errors,
            source="expected",
        )

        actual_by_identity = self._index_items(
            actual_items,
            errors,
            source="actual",
        )

        expected_keys = set(expected_by_identity)
        actual_keys = set(actual_by_identity)

        missing_keys = expected_keys - actual_keys
        unexpected_keys = actual_keys - expected_keys

        for key in missing_keys:
            item = expected_by_identity[key]

            errors.append(f"Missing item: {item.name!r} ({item.parsing_name})")

        for key in unexpected_keys:
            item = actual_by_identity[key]

            errors.append(f"Unexpected item: {item.name!r} ({item.parsing_name})")

        for key in expected_keys & actual_keys:
            expected = expected_by_identity[key]
            actual = actual_by_identity[key]

            if expected.index != actual.index:
                errors.append(
                    f"{expected.name!r}: ListView index changed: "
                    f"expected {expected.index}, "
                    f"actual {actual.index}"
                )

            if expected.name != actual.name:
                errors.append(
                    f"{expected.name!r}: display name changed to {actual.name!r}"
                )

            expected_cell = (
                expected.column,
                expected.row,
            )

            actual_cell = (
                actual.column,
                actual.row,
            )

            if expected_cell != actual_cell:
                errors.append(
                    f"{expected.name!r}: position changed: "
                    f"expected {expected_cell}, "
                    f"actual {actual_cell}"
                )

        return tuple(errors)

    def validate_step(
        self,
        step: MoveStep,
    ) -> tuple[str, ...]:
        """Проверяет объект непосредственно перед перемещением."""

        errors: list[str] = []

        with com_initialized():
            desktop_items = self._scanner.scan()

            # Ищем объект по индексу, который записан в расписании.
            item = next(
                (
                    desktop_item
                    for desktop_item in desktop_items
                    if desktop_item.index == step.index
                ),
                None,
            )

            if item is None:
                return (
                    (
                        f"{step.name!r}: ListView item with "
                        f"index {step.index} was not found"
                    ),
                )

            if item.name != step.name:
                errors.append(
                    f"ListView index {step.index} now belongs to "
                    f"{item.name!r}, expected {step.name!r}"
                )

            if not item.on_primary_monitor:
                errors.append(
                    f"{step.name!r}: item is no longer on the primary monitor"
                )

            if not item.inside_work_area:
                errors.append(f"{step.name!r}: item is outside the primary work area")

            resolution = self._resolver.resolve(item.name)

            if resolution.status != "matched":
                errors.append(f"{step.name!r}: identity status is {resolution.status}")
                return tuple(errors)

            identity = resolution.identity

            if identity is None:
                errors.append(
                    f"{step.name!r}: identity resolution returned no identity"
                )
                return tuple(errors)

            expected_identity = self._identity_key(
                step.identity_type,
                step.parsing_name,
            )

            actual_identity = self._identity_key(
                identity.kind,
                identity.parsing_name,
            )

            if actual_identity != expected_identity:
                errors.append(
                    f"{step.name!r}: identity mismatch at ListView index {step.index}"
                )

            try:
                actual_cell = self._grid.to_cell(
                    item.screen_x,
                    item.screen_y,
                )
            except ValueError as error:
                errors.append(f"{step.name!r}: cannot determine current cell: {error}")
                return tuple(errors)

            expected_cell = (
                step.from_column,
                step.from_row,
            )

            if actual_cell != expected_cell:
                errors.append(
                    f"{step.name!r}: position changed before movement: "
                    f"expected {expected_cell}, actual {actual_cell}"
                )

        return tuple(errors)

    @staticmethod
    def _index_items(
        items: list[CurrentItemState],
        errors: list[str],
        source: str,
    ) -> dict[tuple[str, str], CurrentItemState]:
        """Индексирует объекты по идентичности."""

        result: dict[
            tuple[str, str],
            CurrentItemState,
        ] = {}

        for item in items:
            key = DesktopStateValidator._identity_key(
                item.identity_type,
                item.parsing_name,
            )

            if key in result:
                errors.append(f"Duplicate identity in {source} state: {item.name!r}")
                continue

            result[key] = item

        return result

    @staticmethod
    def _identity_key(
        identity_type: str,
        parsing_name: str,
    ) -> tuple[str, str]:
        """Нормализует идентичность объекта."""

        if identity_type == "filesystem":
            normalized = ntpath.normcase(ntpath.normpath(parsing_name))
        else:
            normalized = parsing_name.casefold()

        return identity_type, normalized
