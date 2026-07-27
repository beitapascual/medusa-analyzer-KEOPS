from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted((_jsonable(item) for item in value), key=str)

    item = getattr(value, "item", None)
    if callable(item) and getattr(value, "shape", None) == ():
        try:
            return _jsonable(item())
        except (TypeError, ValueError):
            pass

    shape = getattr(value, "shape", None)
    dtype = getattr(value, "dtype", None)
    if shape is not None and dtype is not None:
        return {"__type__": type(value).__name__, "shape": list(shape), "dtype": str(dtype)}

    return str(value)


def save_pipeline_config(state: dict[str, Any], output_path: str | Path) -> Path:
    output_dir = Path(str(output_path))
    output_dir.mkdir(parents=True, exist_ok=True)
    config_path = output_dir / "config.json"
    config_path.write_text(
        json.dumps(_jsonable(state), indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return config_path
