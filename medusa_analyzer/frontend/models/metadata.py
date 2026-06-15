from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MetadataSummary:
    file_name: str
    file_path: str
    channels: list[str]
    sampling_rate: float | None = None
    duration_seconds: float | None = None
    n_samples: int | None = None

    @classmethod
    def from_loader_result(cls, result: dict) -> "MetadataSummary":
        return cls(
            file_name=result.get("name", ""),
            file_path=result.get("path", ""),
            channels=list(result.get("channels", [])),
            sampling_rate=result.get("sampling_rate"),
            duration_seconds=result.get("duration_seconds"),
            n_samples=result.get("n_samples"),
        )
