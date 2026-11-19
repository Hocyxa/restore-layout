from desktop.winapi import (
    find_list_view,
    get_client_origin_on_screen,
    get_item_count,
    get_item_position,
    set_item_position,
)


class DesktopMover:
    """Перемещает иконки рабочего стола."""

    TOLERANCE = 2

    def __init__(self) -> None:
        self._hwnd = find_list_view()

    def move_to_screen(
        self,
        index: int,
        screen_x: int,
        screen_y: int,
    ) -> tuple[int, int]:
        """Перемещает иконку в заданные экранные координаты."""

        item_count = get_item_count(self._hwnd)

        if not 0 <= index < item_count:
            raise IndexError(
                f"Индекс элемента {index} вне диапазона 0..{item_count - 1}"
            )

        # Переводим экранные координаты в координаты ListView.
        origin_x, origin_y = get_client_origin_on_screen(self._hwnd)

        client_x = screen_x - origin_x
        client_y = screen_y - origin_y

        set_item_position(
            hwnd=self._hwnd,
            index=index,
            x=client_x,
            y=client_y,
        )

        # Проверяем фактическое положение элемента.
        actual_x, actual_y = get_item_position(
            self._hwnd,
            index,
        )

        if (
            abs(actual_x - client_x) > self.TOLERANCE
            or abs(actual_y - client_y) > self.TOLERANCE
        ):
            raise RuntimeError(
                f"Не удалось подтвердить перемещение элемента "
                f"{index}. "
                f"Ожидалось: ({client_x}, {client_y}), "
                f"получено: ({actual_x}, {actual_y})"
            )

        return (
            actual_x + origin_x,
            actual_y + origin_y,
        )
