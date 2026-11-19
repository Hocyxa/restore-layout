import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from services.models import DesktopSnapshot


class JsonStorage:
    def __init__(self, path: Path) -> None:
        self._path = path

    def save(self, snapshot: DesktopSnapshot) -> None:
        """Сохраняет снимок рабочего стола в JSON."""

        self._path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = asdict(snapshot)
        data["created_at"] = snapshot.created_at.isoformat()

        self._write_atomically(data)

    def _write_atomically(self, data: dict) -> None:
        """Записывает JSON через временный файл."""

        temporary_path = self._path.with_suffix(self._path.suffix + ".tmp")

        try:
            with temporary_path.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    data,
                    file,
                    ensure_ascii=False,
                    indent=4,
                )

            temporary_path.replace(self._path)

        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    def load(self) -> DesktopSnapshot:
        """Загружает снимок рабочего стола из JSON."""

        with self._path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        data["created_at"] = datetime.fromisoformat(data["created_at"])

        from services.models import (
            DesktopItemSnapshot,
            GridSnapshot,
            ItemIdentitySnapshot,
            ItemPositionSnapshot,
            MonitorSnapshot,
        )

        return DesktopSnapshot(
            version=data["version"],
            created_at=data["created_at"],
            monitor=MonitorSnapshot(**data["monitor"]),
            grid=GridSnapshot(**data["grid"]),
            items=tuple(
                DesktopItemSnapshot(
                    name=item["name"],
                    identity=ItemIdentitySnapshot(**item["identity"]),
                    position=ItemPositionSnapshot(**item["position"]),
                )
                for item in data["items"]
            ),
        )

    @property
    def path(self) -> Path:
        return self._path
