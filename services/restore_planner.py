import ntpath
from collections import defaultdict

from desktop.monitor import Monitor
from grid.models import DesktopGrid
from services.models import DesktopSnapshot
from services.restore_models import (
    CurrentItemState,
    IdentityType,
    ItemReference,
    RestoreAction,
    RestorePlan,
)


class RestorePlanner:
    """Формирует план восстановления рабочего стола."""

    def create_plan(
        self,
        snapshot: DesktopSnapshot,
        current_items: list[CurrentItemState],
        current_monitor: Monitor,
        current_grid: DesktopGrid,
        identity_errors: list[str] | None = None,
    ) -> RestorePlan:
        compatibility_errors = self._check_compatibility(
            snapshot,
            current_monitor,
            current_grid,
        )

        conflicts: list[str] = []

        saved_index = self._build_index(
            snapshot.items,
            lambda item: self._identity_key(
                item.identity.type,
                item.identity.parsing_name,
            ),
            "снимке",
            conflicts,
        )

        current_index = self._build_index(
            current_items,
            lambda item: self._identity_key(
                item.identity_type,
                item.parsing_name,
            ),
            "текущем рабочем столе",
            conflicts,
        )

        actions: list[RestoreAction] = []
        missing_items: list[ItemReference] = []
        unexpected_items: list[ItemReference] = []

        # Определяем отсутствующие и совпавшие объекты.
        for key, saved_item in saved_index.items():
            current_item = current_index.get(key)

            if current_item is None:
                missing_items.append(
                    ItemReference(
                        name=saved_item.name,
                        identity_type=saved_item.identity.type,
                        parsing_name=saved_item.identity.parsing_name,
                    )
                )
                continue

            target_column = saved_item.position.column
            target_row = saved_item.position.row

            actions.append(
                RestoreAction(
                    name=saved_item.name,
                    identity_type=saved_item.identity.type,
                    parsing_name=saved_item.identity.parsing_name,
                    current_column=current_item.column,
                    current_row=current_item.row,
                    target_column=target_column,
                    target_row=target_row,
                    index=current_item.index,
                )
            )

        # Определяем новые объекты, отсутствующие в снимке.
        for key, current_item in current_index.items():
            if key not in saved_index:
                unexpected_items.append(
                    ItemReference(
                        name=current_item.name,
                        identity_type=current_item.identity_type,
                        parsing_name=current_item.parsing_name,
                    )
                )

        # Проверяем уникальность целевых ячеек.
        target_cells: dict[tuple[int, int], list[str]] = defaultdict(list)

        for action in actions:
            cell = (action.target_column, action.target_row)
            target_cells[cell].append(action.name)
            if not current_grid.is_valid_cell(
                action.target_column,
                action.target_row,
            ):
                conflicts.append(
                    f"Целевая ячейка объекта {action.name!r} "
                    f"находится за пределами текущей сетки"
                )

        for cell, names in target_cells.items():
            if len(names) > 1:
                conflicts.append(
                    f"Несколько объектов назначены в ячейку {cell}: {', '.join(names)}"
                )

        # Проверяем, что целевые ячейки не заняты новыми объектами.
        unexpected_cells = {
            (item.column, item.row): item
            for item in current_items
            if self._identity_key(
                item.identity_type,
                item.parsing_name,
            )
            not in saved_index
        }

        for cell, item in unexpected_cells.items():
            target_names = [
                action.name
                for action in actions
                if (
                    action.target_column,
                    action.target_row,
                )
                == cell
            ]

            if target_names:
                conflicts.append(
                    f"Целевая ячейка {cell} для "
                    f"{', '.join(target_names)} занята новым объектом "
                    f"{item.name!r}"
                )

        return RestorePlan(
            actions=tuple(actions),
            missing_items=tuple(missing_items),
            unexpected_items=tuple(unexpected_items),
            conflicts=tuple(conflicts),
            compatibility_errors=tuple(compatibility_errors),
            identity_errors=tuple(identity_errors or ()),
        )

    @staticmethod
    def _identity_key(
        identity_type: IdentityType,
        parsing_name: str,
    ) -> tuple[str, str]:
        """Нормализует идентификатор для сравнения."""

        if identity_type == "filesystem":
            normalized = ntpath.normcase(ntpath.normpath(parsing_name))
        else:
            normalized = parsing_name.casefold()

        return identity_type, normalized

    @staticmethod
    def _build_index(
        items,
        key_factory,
        source_name: str,
        conflicts: list[str],
    ) -> dict:
        """Строит индекс объектов и обнаруживает дубликаты."""

        index = {}

        for item in items:
            key = key_factory(item)

            if key in index:
                conflicts.append(
                    f"Дублирующийся идентификатор в {source_name}: {item.name!r}"
                )
                continue

            index[key] = item

        return index

    @staticmethod
    def _check_compatibility(
        snapshot: DesktopSnapshot,
        monitor: Monitor,
        grid: DesktopGrid,
    ) -> list[str]:
        """Проверяет совместимость текущей среды со снимком."""

        errors: list[str] = []
        saved_monitor = snapshot.monitor
        saved_grid = snapshot.grid

        monitor_fields = (
            ("left", monitor.left, saved_monitor.left),
            ("top", monitor.top, saved_monitor.top),
            ("right", monitor.right, saved_monitor.right),
            ("bottom", monitor.bottom, saved_monitor.bottom),
            ("work_left", monitor.work_left, saved_monitor.work_left),
            ("work_top", monitor.work_top, saved_monitor.work_top),
            ("work_right", monitor.work_right, saved_monitor.work_right),
            ("work_bottom", monitor.work_bottom, saved_monitor.work_bottom),
        )

        for field, current, saved in monitor_fields:
            if current != saved:
                errors.append(
                    f"Геометрия монитора изменилась: "
                    f"{field}: сохранено {saved}, сейчас {current}"
                )

        grid_fields = (
            ("origin_x", grid.origin_x, saved_grid.origin_x),
            ("origin_y", grid.origin_y, saved_grid.origin_y),
            ("step_x", grid.step_x, saved_grid.step_x),
            ("step_y", grid.step_y, saved_grid.step_y),
            ("columns", grid.columns, saved_grid.columns),
            ("rows", grid.rows, saved_grid.rows),
        )

        for field, current, saved in grid_fields:
            if current != saved:
                errors.append(
                    f"Параметр сетки изменился: "
                    f"{field}: сохранено {saved}, сейчас {current}"
                )

        return errors
