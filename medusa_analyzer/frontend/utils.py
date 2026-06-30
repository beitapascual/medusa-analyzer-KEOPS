from __future__ import annotations

from pathlib import Path
from typing import Any


def create_metadata_summary(loader_result: dict[str, Any]) -> dict[str, Any]:
    """Create a normalized metadata summary dictionary from one loader result.

    The loader result is the raw dictionary returned by the file loader.
    This function extracts only the fields needed by the frontend.
    """
    file_path = str(loader_result.get("path") or "")
    file_name = str(loader_result.get("name") or loader_result.get("file_name") or Path(file_path).name)
    return {"file_name": file_name, "file_path": file_path,
        "channels": list(loader_result.get("channels") or []), "sampling_rate": loader_result.get("sampling_rate"),
        "duration_seconds": loader_result.get("duration_seconds"), "n_samples": loader_result.get("n_samples"),
        "broadband": loader_result.get("broadband")}


def create_metadata_summaries(loader_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create one normalized metadata summary dictionary per loaded file."""
    return [create_metadata_summary(result) for result in loader_results]
