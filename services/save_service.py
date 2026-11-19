from datetime import UTC, datetime

from desktop.identity import (
    DesktopIdentityResolver,
    com_initialized,
)
from desktop.monitor import Monitor, get_primary_monitor
from desktop.scanner import DesktopScanner
from grid.detector import DesktopGridDetector
from grid.models import DesktopGrid
from services.models import (
    DesktopItemSnapshot,
    DesktopSnapshot,
    GridSnapshot,
    ItemIdentitySnapshot,
    ItemPositionSnapshot,
    MonitorSnapshot,
)


class SaveService:
    VERSION = 1

    def __init__(
        self,
        monitor: Monitor | None,
        scanner: DesktopScanner | None,
        grid_detector: DesktopGridDetector | None,
    ) -> None:
        self._monitor: Monitor = monitor or get_primary_monitor()
        self._scanner = scanner or DesktopScanner(self._monitor)
        self._grid_detector = grid_detector or DesktopGridDetector(self._monitor)
        with com_initialized():
            self._identity_resolver = DesktopIdentityResolver()

    def create_snapshot(self) -> DesktopSnapshot:
        """Создаёт снимок текущего состояния рабочего стола."""

        grid = self._grid_detector.detect()
        desktop_items = self._scanner.scan()

        primary_items = [item for item in desktop_items if item.on_primary_monitor]

        resolved_items = []
        with com_initialized():
            for item in primary_items:
                resolution = self._identity_resolver.resolve(item.name)

                if resolution.status != "matched":
                    raise RuntimeError(
                        f"Не удалось однозначно идентифицировать объект "
                        f"{item.name!r}: {resolution.status}"
                    )

                identity = resolution.identity

                if identity is None:
                    raise RuntimeError(
                        f"Для объекта {item.name!r} не удалось получить идентификатор"
                    )

                column, row = grid.to_cell(
                    item.screen_x,
                    item.screen_y,
                )

                resolved_items.append(
                    DesktopItemSnapshot(
                        name=item.name,
                        identity=ItemIdentitySnapshot(
                            type=identity.kind,
                            parsing_name=identity.parsing_name,
                        ),
                        position=ItemPositionSnapshot(
                            column=column,
                            row=row,
                        ),
                    )
                )

        return DesktopSnapshot(
            version=self.VERSION,
            created_at=datetime.now(UTC),
            monitor=self._create_monitor_snapshot(self._monitor),
            grid=self._create_grid_snapshot(grid),
            items=tuple(resolved_items),
        )

    @staticmethod
    def _create_monitor_snapshot(
        monitor: Monitor,
    ) -> MonitorSnapshot:
        return MonitorSnapshot(
            left=monitor.left,
            top=monitor.top,
            right=monitor.right,
            bottom=monitor.bottom,
            work_left=monitor.work_left,
            work_top=monitor.work_top,
            work_right=monitor.work_right,
            work_bottom=monitor.work_bottom,
        )

    @staticmethod
    def _create_grid_snapshot(
        grid: DesktopGrid,
    ) -> GridSnapshot:
        return GridSnapshot(
            origin_x=grid.origin_x,
            origin_y=grid.origin_y,
            step_x=grid.step_x,
            step_y=grid.step_y,
            columns=grid.columns,
            rows=grid.rows,
        )
