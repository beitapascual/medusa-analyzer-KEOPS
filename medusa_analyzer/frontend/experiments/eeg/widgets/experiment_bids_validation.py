from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from medusa_analyzer.frontend.validation.bids_validator import validate_bids_dataset


DEFAULT_RAW_EXTENSIONS = [".edf", ".vhdr", ".vmrk", ".eeg", ".set", ".fdt", ".bdf", ".mpl"]
FULL_RECORDING_EVENT = "full_recording"


def load_eeg_bids_dataset(root: str | Path, config: dict[str, Any] | None = None,
    progress_callback: Callable[[int], None] | None = None,
    log_callback: Callable[[str, str], None] | None = None) -> dict[str, Any]:
    config = dict(config or {})
    allowed_datatypes = [str(item).lower() for item in config.get("allowed_datatypes", ["eeg"])]
    allowed_signal_types = {str(item).upper() for item in config.get("allowed_signal_types", allowed_datatypes)}
    if log_callback:
        log_callback("Checking EEG-compatible BIDS recordings.", "info")
    inventory = validate_bids_dataset(root, allowed_datatypes=allowed_datatypes,
        raw_extensions=config.get("raw_extensions", DEFAULT_RAW_EXTENSIONS),
        progress_callback=progress_callback, log_callback=log_callback)

    if inventory["errors"]:
        raise ValueError("\n".join(inventory["errors"][:8]))

    warnings = list(inventory["warnings"])
    groups: dict[tuple[Any, ...], dict[str, Any]] = {}
    for recording in inventory["recordings"]:
        metadata = recording["metadata"]
        try:
            sampling_frequency = float(metadata["SamplingFrequency"])
        except (KeyError, TypeError, ValueError):
            warnings.append(f"Skipping {recording['relative_path']}: missing or invalid SamplingFrequency.")
            continue

        channels = recording["tables"].get("channels") or []
        signal_rows = [row for row in channels
            if str(row.get("type", "")).strip().upper() in allowed_signal_types]
        if not signal_rows:
            warnings.append(f"Skipping {recording['relative_path']}: no compatible channels.tsv rows.")
            continue

        entities = recording["entities"]
        task_info = metadata.get("TaskInformation") if isinstance(metadata.get("TaskInformation"), dict) else {}
        task_nested = next((value for value in task_info.values() if isinstance(value, dict)), {})
        task = entities.get("task") or metadata.get("TaskName") or task_info.get("TaskName") or task_info.get("Taskname")
        task = task or task_nested.get("TaskName") or task_nested.get("Taskname") or "n/a"

        channel_names = tuple(str(row.get("name", "")).strip() for row in signal_rows if row.get("name"))
        channel_types = tuple(str(row.get("type", "")).strip().upper() for row in signal_rows if row.get("name"))
        reference = str(metadata.get("EEGReference") or "n/a")
        events = recording["tables"].get("events") or []
        event_columns = tuple(events[0].keys()) if events else ()
        duration_events: set[str] = set()
        instant_events: set[str] = set()
        for row in events:
            event_name = str(row.get("trial_type") or row.get("value") or "").strip()
            if not event_name:
                continue
            try:
                duration = float(str(row.get("duration") or "0").replace(",", "."))
            except ValueError:
                duration = 0.0
            if duration >= 1.0:
                duration_events.add(event_name)
            else:
                instant_events.add(event_name)
        duration_events.add(FULL_RECORDING_EVENT)
        duration_event_types = tuple([FULL_RECORDING_EVENT] + sorted(duration_events - {FULL_RECORDING_EVENT}))
        instant_event_types = tuple(sorted(instant_events))
        event_types = tuple(sorted(duration_events | instant_events))
        key = (recording["datatype"], task, sampling_frequency, reference, channel_names, channel_types,
            event_columns, duration_event_types, instant_event_types)

        group = groups.setdefault(key, {
            "datatype": recording["datatype"],
            "task": task,
            "sampling_frequency": sampling_frequency,
            "reference": reference,
            "channel_set": list(channel_names),
            "event_columns": list(event_columns),
            "event_types": list(event_types),
            "duration_events": list(duration_event_types),
            "instant_events": list(instant_event_types),
            "raw_extensions": set(),
            "recordings": [],
        })
        group["raw_extensions"].add(recording["extension"])
        group["recordings"].append({
            "path": recording["path"],
            "relative_path": recording["relative_path"],
            "subject": entities.get("sub"),
            "session": entities.get("ses"),
            "run": entities.get("run"),
            "datatype": recording["datatype"],
            "extension": recording["extension"],
            "json_sidecars": recording["json_sidecars"],
            "sidecars": recording["sidecars"],
        })

    if not groups:
        detail = "\n".join(warnings[:8])
        raise ValueError(f"No EEG-compatible BIDS recordings found.\n{detail}".strip())

    group_list = sorted(groups.values(), key=lambda group: len(group["recordings"]), reverse=True)
    for index, group in enumerate(group_list, start=1):
        recordings = group["recordings"]
        group["id"] = f"group-{index}"
        group["n_recordings"] = len(recordings)
        group["subjects"] = sorted({item["subject"] for item in recordings if item.get("subject")})
        group["sessions"] = sorted({item["session"] for item in recordings if item.get("session")})
        group["n_channels"] = len(group["channel_set"])
        group["raw_extensions"] = sorted(group["raw_extensions"])

    if len(group_list) > 1:
        warnings.append(f"Detected {len(group_list)} different BIDS recording configuration(s).")
    if log_callback:
        for warning in warnings:
            log_callback(warning, "warning")

    return {"root": inventory["root"], "groups": group_list, "warnings": warnings}


__all__ = ["load_eeg_bids_dataset"]
