from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonStore:
    def write(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

    def read(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))
