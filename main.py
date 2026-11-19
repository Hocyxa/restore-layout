import argparse
import sys
from pathlib import Path

from desktop.identity import (
    DesktopIdentityResolver,
    com_initialized,
)
from desktop.monitor import get_primary_monitor
from desktop.mover import DesktopMover
from desktop.scanner import DesktopScanner
from grid.detector import DesktopGridDetector
from grid.models import DesktopGrid
from services.desktop_state_validator import DesktopStateValidator
from services.json_storage import JsonStorage
from services.move_scheduler import MoveScheduler
from services.restore_executor import RestoreExecutor
from services.restore_models import CurrentItemState
from services.restore_planner import RestorePlanner
from services.save_service import SaveService

BASE_DIR = Path(__file__).resolve().parent
SNAPSHOT_PATH = BASE_DIR / "data" / "desktop-layout.json"


def create_parser() -> argparse.ArgumentParser:
    """Создаёт CLI-интерфейс приложения."""

    parser = argparse.ArgumentParser(
        description="Save and restore Windows desktop icon layout.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser(
        "save",
        help="Save current desktop layout.",
    )

    restore_parser = subparsers.add_parser(
        "restore",
        help="Restore desktop layout from saved snapshot.",
    )

    restore_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and validate restore plan without moving icons.",
    )

    return parser


def print_plan(plan) -> None:
    """Выводит план восстановления."""

    print("\nRESTORE PLAN")
    print("-" * 80)

    print(f"Actions: {len(plan.actions)}")
    print(f"Missing: {len(plan.missing_items)}")
    print(f"Unexpected: {len(plan.unexpected_items)}")
    print(f"Conflicts: {len(plan.conflicts)}")
    print(f"Identity errors: {len(plan.identity_errors)}")
    print(f"Compatibility errors: {len(plan.compatibility_errors)}")
    print(f"Safe to restore: {plan.is_safe}")

    if plan.compatibility_errors:
        print("\nCOMPATIBILITY ERRORS")
        for error in plan.compatibility_errors:
            print(f"- {error}")

    if plan.identity_errors:
        print("\nIDENTITY ERRORS")
        for error in plan.identity_errors:
            print(f"- {error}")

    if plan.conflicts:
        print("\nCONFLICTS")
        for conflict in plan.conflicts:
            print(f"- {conflict}")

    if plan.missing_items:
        print("\nMISSING ITEMS")
        for item in plan.missing_items:
            print(f"- {item.name}")

    if plan.unexpected_items:
        print("\nUNEXPECTED ITEMS")
        for item in plan.unexpected_items:
            print(f"- {item.name}: {item.parsing_name}")

    movements = [
        action
        for action in plan.actions
        if (
            action.current_column,
            action.current_row,
        )
        != (
            action.target_column,
            action.target_row,
        )
    ]

    if movements:
        print("\nMOVEMENTS")

        for action in movements:
            current = (
                action.current_column,
                action.current_row,
            )
            target = (
                action.target_column,
                action.target_row,
            )

            print(f"{action.name}: {current} -> {target}")


def print_schedule(schedule) -> None:
    """Выводит расписание перемещений."""

    print("\nMOVE SCHEDULE")
    print("-" * 80)

    print(f"Total steps: {len(schedule.steps)}")
    print(f"Temporary moves: {schedule.temporary_moves}")

    for number, step in enumerate(schedule.steps, start=1):
        move_type = "TEMPORARY" if step.is_temporary else "NORMAL"

        source = (
            step.from_column,
            step.from_row,
        )
        target = (
            step.to_column,
            step.to_row,
        )

        print(
            f"{number}. [{move_type}] "
            f"{step.name}: {source} -> {target} "
            f"(index={step.index})"
        )


def print_execution_result(result) -> None:
    """Выводит результат восстановления."""

    print("\nRESTORE RESULT")
    print("-" * 80)

    print(f"Success: {result.success}")
    print(f"Completed steps: {result.completed_steps}")
    print(f"Rolled back: {result.rolled_back}")

    if result.error:
        print(f"Error: {result.error}")

    if result.rollback_errors:
        print("\nROLLBACK ERRORS")

        for error in result.rollback_errors:
            print(f"- {error}")


def collect_current_items(
    scanner: DesktopScanner,
    resolver: DesktopIdentityResolver,
    grid: DesktopGrid,
) -> tuple[list[CurrentItemState], list[str]]:
    """Собирает текущее состояние рабочего стола."""

    current_items: list[CurrentItemState] = []
    identity_errors: list[str] = []

    for item in scanner.scan():
        if not item.on_primary_monitor:
            continue

        if not item.inside_work_area:
            continue

        resolution = resolver.resolve(item.name)

        if resolution.status != "matched":
            identity_errors.append(
                f"{item.name}: identity status is {resolution.status}"
            )
            continue

        identity = resolution.identity

        if identity is None:
            identity_errors.append(
                f"{item.name}: identity resolution returned no identity"
            )
            continue

        column, row = grid.to_cell(
            item.screen_x,
            item.screen_y,
        )

        current_items.append(
            CurrentItemState(
                index=item.index,
                name=item.name,
                identity_type=identity.kind,
                parsing_name=identity.parsing_name,
                column=column,
                row=row,
            )
        )

    return current_items, identity_errors


def save_layout() -> None:
    """Сохраняет текущее расположение рабочего стола."""

    print("DESKTOP LAYOUT SAVE")
    print("=" * 80)

    monitor = get_primary_monitor()
    scanner = DesktopScanner(monitor)
    grid_detector = DesktopGridDetector(monitor)

    save_service = SaveService(
        monitor=monitor,
        scanner=scanner,
        grid_detector=grid_detector,
    )

    snapshot = save_service.create_snapshot()

    storage = JsonStorage(SNAPSHOT_PATH)
    storage.save(snapshot)

    print("\nSAVE RESULT")
    print("-" * 80)
    print(f"File: {SNAPSHOT_PATH}")
    print(f"Items saved: {len(snapshot.items)}")
    print(f"Grid: {snapshot.grid.columns}x{snapshot.grid.rows}")
    print(f"Monitor: {monitor.width}x{monitor.height}")
    print("\nDesktop layout successfully saved.")


def restore_layout(dry_run: bool = False) -> None:
    """Строит и выполняет план восстановления."""

    print("DESKTOP LAYOUT RESTORE")
    print("=" * 80)

    # 1. Загружаем снимок.
    storage = JsonStorage(SNAPSHOT_PATH)
    snapshot = storage.load()

    print(f"Snapshot: {SNAPSHOT_PATH}")
    print(f"Saved items: {len(snapshot.items)}")

    # 2. Получаем текущую конфигурацию.
    monitor = get_primary_monitor()
    scanner = DesktopScanner(monitor)
    grid = DesktopGridDetector(monitor).detect()

    print(f"Monitor: {monitor.width}x{monitor.height}")
    print(f"Grid: {grid.columns}x{grid.rows}")

    # 3. Сканируем рабочий стол и определяем идентичность объектов.
    with com_initialized():
        resolver = DesktopIdentityResolver()

        current_items, identity_errors = collect_current_items(
            scanner=scanner,
            resolver=resolver,
            grid=grid,
        )

    print(f"Current items: {len(current_items)}")

    # 4. Строим план восстановления.
    planner = RestorePlanner()

    plan = planner.create_plan(
        snapshot=snapshot,
        current_items=current_items,
        current_monitor=monitor,
        current_grid=grid,
        identity_errors=identity_errors,
    )

    print_plan(plan)

    if not plan.is_safe:
        print("\nRestore aborted: plan is not safe.")
        return

    # 5. Формируем расписание.
    scheduler = MoveScheduler()

    schedule = scheduler.create_schedule(
        plan=plan,
        current_items=current_items,
        columns=grid.columns,
        rows=grid.rows,
    )

    print_schedule(schedule)

    # 6. Создаём валидатор.
    validator = DesktopStateValidator(
        scanner=scanner,
        resolver=resolver,
        grid=grid,
    )

    # 7. Проверяем, не изменился ли рабочий стол.
    validation_errors = validator.validate(current_items)

    if validation_errors:
        print("\nDESKTOP STATE VALIDATION FAILED")

        for error in validation_errors:
            print(f"- {error}")

        print("\nRestore aborted: desktop state has changed.")
        return

    print("\nDesktop state validation passed.")

    if not schedule.steps:
        print("\nDesktop layout is already restored.")
        return

    # 8. Режим предварительного просмотра.
    if dry_run:
        print("\nDry run. No icons were moved.")
        return

    # 9. Подтверждение пользователя.
    print("\nWARNING: Desktop icons will be moved.")
    answer = input("Continue? [y/N]: ").strip().lower()

    if answer not in ("y", "yes", "д", "да"):
        print("\nRestore cancelled.")
        return

    # 10. Выполняем восстановление.
    executor = RestoreExecutor(
        mover=DesktopMover(),
        grid=grid,
        validator=validator,
    )

    result = executor.execute(
        schedule=schedule,
        current_items=current_items,
    )

    print_execution_result(result)


def main() -> int:
    parser = create_parser()
    args = parser.parse_args()

    try:
        if args.command == "save":
            save_layout()

        elif args.command == "restore":
            restore_layout(
                dry_run=args.dry_run,
            )

        return 0

    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        return 130

    except Exception as error:
        print(f"\nERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
