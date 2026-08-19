"""Output persistence for exports."""

import json
from pathlib import Path


class JsonExportWriter:
    def __init__(self, destination: Path = Path("/output/conversations.json")) -> None:
        self._destination = destination

    def write(self, accounts: list[dict[str, object]]) -> Path:
        self._destination.parent.mkdir(parents=True, exist_ok=True)
        self._destination.write_text(json.dumps(accounts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return self._destination
