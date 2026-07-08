from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Callable


RAW_EXTENSIONS = {".edf", ".vhdr", ".vmrk", ".eeg", ".set", ".fdt", ".bdf", ".mpl"}
SIDE_TABLE_SUFFIXES = ("channels", "events", "electrodes", "optodes")


def parse_bids_name(path: Path) -> dict[str, Any]:
    stem = path.name[:-7] if path.name.lower().endswith(".tsv.gz") else path.stem
    parts = stem.split("_")
    entities: dict[str, str] = {}
    for part in parts[:-1]:
        if "-" in part:
            key, value = part.split("-", 1)
            entities[key] = value
    return {"suffix": parts[-1].lower() if parts else "", "entities": entities}


def validate_bids_dataset(root: str | Path, allowed_datatypes: list[str] | None = None,
    raw_extensions: list[str] | None = None, progress_callback: Callable[[int], None] | None = None,
    log_callback: Callable[[str, str], None] | None = None) -> dict[str, Any]:
    root = Path(root)
    if not root.is_dir():
        raise ValueError(f"BIDS folder does not exist: {root}")

    allowed = {datatype.lower() for datatype in (allowed_datatypes or [])}
    extensions = {ext.lower() if str(ext).startswith(".") else f".{str(ext).lower()}"
        for ext in (raw_extensions or RAW_EXTENSIONS)}
    errors: list[str] = []
    warnings: list[str] = []

    if log_callback:
        log_callback(f"Validating BIDS dataset: {root}", "info")
    if progress_callback:
        progress_callback(5)
    if root.name.startswith(("sub-", "ses-")):
        errors.append("Select the BIDS dataset root, not a subject or session folder.")
    if not (root / "dataset_description.json").is_file():
        errors.append("Missing dataset_description.json at BIDS root.")
    if not any(path.is_dir() and path.name.startswith("sub-") for path in root.iterdir()):
        errors.append("No sub-* folders found at BIDS root.")

    files = [path for path in root.rglob("*") if path.is_file()]
    json_files = [path for path in files if path.suffix.lower() == ".json"]
    tsv_files = [path for path in files if path.suffix.lower() == ".tsv"]
    recordings: list[dict[str, Any]] = []
    if log_callback:
        log_callback(f"Found {len(files)} file(s): {len(json_files)} JSON sidecar(s), {len(tsv_files)} TSV sidecar(s).",
            "info")
        if allowed:
            log_callback(f"Allowed datatype(s): {', '.join(sorted(allowed))}.", "info")
        log_callback(f"Allowed raw extension(s): {', '.join(sorted(extensions))}.", "info")

    for index, path in enumerate(files, start=1):
        ext = path.suffix.lower()
        if ext not in extensions or ext in {".json", ".tsv"}:
            continue
        if ext == ".vmrk" or (ext == ".eeg" and path.with_suffix(".vhdr").is_file()):
            continue
        if ext == ".fdt" and path.with_suffix(".set").is_file():
            continue

        datatype = path.parent.name.lower()
        if allowed and datatype not in allowed:
            continue

        parsed = parse_bids_name(path)
        entities = parsed["entities"]
        if not entities.get("sub"):
            warnings.append(f"Raw file without sub- entity: {path.relative_to(root)}")
        if parsed["suffix"] != datatype:
            warnings.append(f"Raw suffix '{parsed['suffix']}' does not match datatype '{datatype}': {path.relative_to(root)}")

        metadata, json_sidecars = {}, []
        for sidecar, _ in sorted(_applicable_sidecars(root, path.parent, entities, parsed["suffix"], json_files),
            key=lambda item: _sidecar_score(root, item[0], item[1])):
            try:
                data = _read_json(sidecar)
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"Could not read JSON sidecar {sidecar.relative_to(root)}: {exc}")
                continue
            metadata.update(data)
            json_sidecars.append(str(sidecar))

        sidecars: dict[str, str] = {}
        tables: dict[str, list[dict[str, str]]] = {}
        for suffix in SIDE_TABLE_SUFFIXES:
            matches = _applicable_sidecars(root, path.parent, entities, suffix, tsv_files)
            if not matches:
                continue
            sidecar, _ = max(matches, key=lambda item: _sidecar_score(root, item[0], item[1]))
            sidecars[f"{suffix}_tsv"] = str(sidecar)
            try:
                tables[suffix] = _read_tsv(sidecar)
            except OSError as exc:
                errors.append(f"Could not read TSV sidecar {sidecar.relative_to(root)}: {exc}")

        recordings.append({
            "path": str(path),
            "relative_path": str(path.relative_to(root)),
            "datatype": datatype,
            "suffix": parsed["suffix"],
            "extension": ext,
            "entities": entities,
            "metadata": metadata,
            "json_sidecars": json_sidecars,
            "sidecars": sidecars,
            "tables": tables,
        })
        if progress_callback and index % 20 == 0:
            progress_callback(min(90, 5 + int(index / max(len(files), 1) * 85)))

    if not recordings:
        suffix = f" for datatypes {sorted(allowed)}" if allowed else ""
        errors.append(f"No compatible raw recordings found{suffix}.")

    if progress_callback:
        progress_callback(100)
    if log_callback:
        log_callback(f"Found {len(recordings)} raw recording(s).", "info")
        for error in errors:
            log_callback(error, "error")
        for warning in warnings:
            log_callback(warning, "warning")

    return {"root": str(root), "is_valid": not errors, "errors": errors, "warnings": warnings,
        "recordings": recordings}


def _applicable_sidecars(root: Path, recording_dir: Path, entities: dict[str, str], suffix: str,
    candidates: list[Path]) -> list[tuple[Path, dict[str, str]]]:
    matches = []
    for path in candidates:
        parsed = parse_bids_name(path)
        if parsed["suffix"] != suffix or not _is_parent(path.parent, recording_dir):
            continue
        side_entities = parsed["entities"]
        if all(entities.get(key) == value for key, value in side_entities.items()):
            matches.append((path, side_entities))
    return matches


def _sidecar_score(root: Path, path: Path, entities: dict[str, str]) -> tuple[int, int]:
    try:
        depth = len(path.parent.relative_to(root).parts)
    except ValueError:
        depth = 0
    return depth, len(entities)


def _is_parent(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


__all__ = ["parse_bids_name", "validate_bids_dataset"]
