import ntpath

from services.restore_models import (
    CurrentItemState,
    IdentityType,
    MoveSchedule,
    MoveStep,
    RestorePlan,
)


class MoveScheduler:
    """Формирует безопасную последовательность перемещений."""

    def create_schedule(
        self,
        plan: RestorePlan,
        current_items: list[CurrentItemState],
        columns: int,
        rows: int,
    ) -> MoveSchedule:
        if not plan.is_safe:
            raise ValueError(
                "Невозможно построить последовательность: "
                "план восстановления содержит ошибки"
            )

        positions = {}
        occupancy = {}

        # Формируем карту текущего расположения всех объектов.
        for item in current_items:
            key = self._identity_key(
                item.identity_type,
                item.parsing_name,
            )

            cell = (item.column, item.row)

            if key in positions:
                raise ValueError(f"Повторяющийся идентификатор: {item.name}")

            if cell in occupancy:
                raise ValueError(f"Несколько объектов находятся в ячейке {cell}")

            positions[key] = item
            occupancy[cell] = key

        pending = {}

        # Формируем список объектов, которые действительно нужно переместить.
        for action in plan.actions:
            key = self._identity_key(
                action.identity_type,
                action.parsing_name,
            )

            if key not in positions:
                raise ValueError(
                    f"Объект {action.name!r} отсутствует в текущем состоянии"
                )

            current_item = positions[key]

            current_cell = (
                current_item.column,
                current_item.row,
            )

            action_cell = (
                action.current_column,
                action.current_row,
            )

            if current_cell != action_cell:
                raise ValueError(
                    f"Текущее положение объекта {action.name!r} "
                    "изменилось после формирования RestorePlan"
                )

            target_cell = (
                action.target_column,
                action.target_row,
            )

            if not self._is_valid_cell(
                target_cell,
                columns,
                rows,
            ):
                raise ValueError(
                    f"Целевая ячейка {target_cell} объекта {action.name!r} вне сетки"
                )

            if current_cell != target_cell:
                pending[key] = action

        # Целевые ячейки всех объектов резервируем.
        reserved_cells = {
            (
                action.target_column,
                action.target_row,
            )
            for action in plan.actions
        }

        steps = []
        temporary_moves = 0

        while pending:
            movable_key = None

            # Ищем объект, целевая ячейка которого свободна.
            for key, action in pending.items():
                target_cell = (
                    action.target_column,
                    action.target_row,
                )

                if target_cell not in occupancy:
                    movable_key = key
                    break

            if movable_key is not None:
                action = pending.pop(movable_key)

                current_item = positions[movable_key]

                from_cell = (
                    current_item.column,
                    current_item.row,
                )

                to_cell = (
                    action.target_column,
                    action.target_row,
                )

                self._move_in_memory(
                    key=movable_key,
                    from_cell=from_cell,
                    to_cell=to_cell,
                    occupancy=occupancy,
                    positions=positions,
                )

                steps.append(
                    self._create_step(
                        action=action,
                        from_cell=from_cell,
                        to_cell=to_cell,
                    )
                )

                continue

            # Свободных целевых ячеек нет: обнаружен цикл.
            temporary_cell = self._find_free_cell(
                columns=columns,
                rows=rows,
                occupancy=occupancy,
                reserved_cells=reserved_cells,
            )

            if temporary_cell is None:
                raise RuntimeError(
                    "Не удалось разрешить цикл: в сетке нет свободной временной ячейки"
                )

            movable_key = next(iter(pending))
            action = pending[movable_key]

            current_item = positions[movable_key]

            from_cell = (
                current_item.column,
                current_item.row,
            )

            # Перемещаем объект во временную ячейку.
            self._move_in_memory(
                key=movable_key,
                from_cell=from_cell,
                to_cell=temporary_cell,
                occupancy=occupancy,
                positions=positions,
            )

            steps.append(
                self._create_step(
                    action=action,
                    from_cell=from_cell,
                    to_cell=temporary_cell,
                    is_temporary=True,
                )
            )

            temporary_moves += 1

        return MoveSchedule(
            steps=tuple(steps),
            temporary_moves=temporary_moves,
        )

    @staticmethod
    def _identity_key(
        identity_type: IdentityType,
        parsing_name: str,
    ) -> tuple[str, str]:
        if identity_type == "filesystem":
            normalized = ntpath.normcase(ntpath.normpath(parsing_name))
        else:
            normalized = parsing_name.casefold()

        return identity_type, normalized

    @staticmethod
    def _is_valid_cell(
        cell: tuple[int, int],
        columns: int,
        rows: int,
    ) -> bool:
        column, row = cell

        return 0 <= column < columns and 0 <= row < rows

    @staticmethod
    def _find_free_cell(
        columns: int,
        rows: int,
        occupancy: dict,
        reserved_cells: set,
    ) -> tuple[int, int] | None:
        for row in range(rows):
            for column in range(columns):
                cell = (column, row)

                if cell in occupancy:
                    continue

                if cell in reserved_cells:
                    continue

                return cell

        return None

    @staticmethod
    def _move_in_memory(
        key: tuple[str, str],
        from_cell: tuple[int, int],
        to_cell: tuple[int, int],
        occupancy: dict,
        positions: dict,
    ) -> None:
        if to_cell in occupancy:
            raise RuntimeError(f"Попытка перемещения в занятую ячейку {to_cell}")

        item = positions[key]

        del occupancy[from_cell]
        occupancy[to_cell] = key

        positions[key] = CurrentItemState(
            name=item.name,
            identity_type=item.identity_type,
            parsing_name=item.parsing_name,
            column=to_cell[0],
            row=to_cell[1],
            index=item.index,
        )

    @staticmethod
    def _create_step(
        action,
        from_cell: tuple[int, int],
        to_cell: tuple[int, int],
        is_temporary: bool = False,
    ) -> MoveStep:
        return MoveStep(
            name=action.name,
            identity_type=action.identity_type,
            parsing_name=action.parsing_name,
            from_column=from_cell[0],
            from_row=from_cell[1],
            to_column=to_cell[0],
            to_row=to_cell[1],
            is_temporary=is_temporary,
            index=action.index,
        )
