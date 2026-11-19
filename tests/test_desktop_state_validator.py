from contextlib import nullcontext
from types import SimpleNamespace

import pytest

import services.desktop_state_validator as validator_module
from desktop.scanner import DesktopItem
from grid.models import DesktopGrid
from services.desktop_state_validator import DesktopStateValidator
from services.restore_models import MoveStep


class FakeScanner:
    def __init__(self, items: list[DesktopItem]) -> None:
        self.items = items

    def scan(self) -> list[DesktopItem]:
        return self.items


class FakeResolver:
    def __init__(self, identities: dict[str, tuple[str, str]]) -> None:
        self.identities = identities

    def resolve(self, name: str):
        identity = self.identities.get(name)

        if identity is None:
            return SimpleNamespace(
                status="unresolved",
                identity=None,
            )

        kind, parsing_name = identity

        return SimpleNamespace(
            status="matched",
            identity=SimpleNamespace(
                kind=kind,
                parsing_name=parsing_name,
            ),
        )


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
def desktop_item() -> DesktopItem:
    # Ячейка (24, 4):
    # screen_x = 22 + 24 * 76 = 1846
    # screen_y = 2 + 4 * 84 = 338

    return DesktopItem(
        index=27,
        name="Works",
        client_x=0,
        client_y=0,
        screen_x=1846,
        screen_y=338,
        on_primary_monitor=True,
        inside_work_area=True,
    )


@pytest.fixture
def move_step() -> MoveStep:
    return MoveStep(
        index=27,
        name="Works",
        identity_type="filesystem",
        parsing_name=r"C:\Users\User\Desktop\Works",
        from_column=24,
        from_row=4,
        to_column=0,
        to_row=0,
    )


@pytest.fixture(autouse=True)
def mock_com_initialized(monkeypatch):
    monkeypatch.setattr(
        validator_module,
        "com_initialized",
        nullcontext,
    )


def create_validator(
    grid: DesktopGrid,
    items: list[DesktopItem],
    identities: dict[str, tuple[str, str]],
) -> DesktopStateValidator:
    return DesktopStateValidator(
        scanner=FakeScanner(items),  # type: ignore
        resolver=FakeResolver(identities),  # type: ignore
        grid=grid,
    )


def test_validate_step_success(
    grid,
    desktop_item,
    move_step,
):
    validator = create_validator(
        grid=grid,
        items=[desktop_item],
        identities={
            "Works": (
                "filesystem",
                r"C:\Users\User\Desktop\Works",
            ),
        },
    )

    errors = validator.validate_step(move_step)

    assert errors == ()


def test_validate_step_item_not_found(
    grid,
    move_step,
):
    validator = create_validator(
        grid=grid,
        items=[],
        identities={},
    )

    errors = validator.validate_step(move_step)

    assert len(errors) == 1
    assert "index 27 was not found" in errors[0]


def test_validate_step_index_belongs_to_another_item(
    grid,
    desktop_item,
    move_step,
):
    another_item = DesktopItem(
        index=27,
        name="Another item",
        client_x=0,
        client_y=0,
        screen_x=1846,
        screen_y=338,
        on_primary_monitor=True,
        inside_work_area=True,
    )

    validator = create_validator(
        grid=grid,
        items=[another_item],
        identities={
            "Another item": (
                "filesystem",
                r"C:\Users\User\Desktop\Another item",
            ),
        },
    )

    errors = validator.validate_step(move_step)

    assert any("now belongs to" in error for error in errors)


def test_validate_step_identity_mismatch(
    grid,
    desktop_item,
    move_step,
):
    validator = create_validator(
        grid=grid,
        items=[desktop_item],
        identities={
            "Works": (
                "filesystem",
                r"C:\Users\User\Desktop\AnotherFolder",
            ),
        },
    )

    errors = validator.validate_step(move_step)

    assert any("identity mismatch" in error for error in errors)


def test_validate_step_position_changed(
    grid,
    desktop_item,
    move_step,
):
    moved_item = DesktopItem(
        index=27,
        name="Works",
        client_x=0,
        client_y=0,
        screen_x=1846,
        screen_y=422,
        on_primary_monitor=True,
        inside_work_area=True,
    )

    validator = create_validator(
        grid=grid,
        items=[moved_item],
        identities={
            "Works": (
                "filesystem",
                r"C:\Users\User\Desktop\Works",
            ),
        },
    )

    errors = validator.validate_step(move_step)

    assert any("position changed before movement" in error for error in errors)


def test_validate_step_outside_work_area(
    grid,
    desktop_item,
    move_step,
):
    outside_item = DesktopItem(
        index=27,
        name="Works",
        client_x=0,
        client_y=0,
        screen_x=1846,
        screen_y=1038,
        on_primary_monitor=True,
        inside_work_area=False,
    )

    validator = create_validator(
        grid=grid,
        items=[outside_item],
        identities={
            "Works": (
                "filesystem",
                r"C:\Users\User\Desktop\Works",
            ),
        },
    )

    errors = validator.validate_step(move_step)

    assert any("outside the primary work area" in error for error in errors)
