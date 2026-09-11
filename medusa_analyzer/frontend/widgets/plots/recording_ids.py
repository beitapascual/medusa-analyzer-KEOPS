from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


_BASE_IGNORED_PREFIXES = ("sub", "param", "band")
_RAW_RECORDING_IGNORED_PREFIXES = (*_BASE_IGNORED_PREFIXES, "segment")
_SESSION_PREFIX = "ses"


def normalize_recording_id(value: Any, ignored_entity_prefixes: Iterable[str] = ()) -> str:
    """Build the logical recording id used by plot feature assignment and lookup."""
    return _normalize_stem(_stem(value), (*_BASE_IGNORED_PREFIXES, *ignored_entity_prefixes))


def normalize_recording_base_id(value: Any, ignored_entity_prefixes: Iterable[str] = ()) -> str:
    stem = _stem(value)
    param_index = stem.find("_param-")
    if param_index >= 0:
        stem = stem[:param_index]
    return _normalize_stem(stem, (*_RAW_RECORDING_IGNORED_PREFIXES, *ignored_entity_prefixes))


def is_parameter_recording_file(value: Any) -> bool:
    return "_param-" in _stem(value)


def _normalize_stem(stem: str, ignored_entity_prefixes: Iterable[str]) -> str:
    ignored_prefixes = _normalized_prefixes((*_BASE_IGNORED_PREFIXES, *ignored_entity_prefixes))
    parts = stem.split("_")
    cleaned = [part for part in parts
        if part and not any(part.startswith(f"{prefix}-") for prefix in ignored_prefixes)]
    return "_".join(cleaned) or stem


def recording_ignored_prefixes_from_recordings(recordings: Iterable[Any]) -> tuple[str, ...]:
    session_values = [_session_value(recording) for recording in recordings]
    sessions = {session for session in session_values if session}
    has_sessionless_recordings = any(not session for session in session_values)
    return (_SESSION_PREFIX,) if len(sessions) == 1 and has_sessionless_recordings else ()


def recording_ignored_prefixes_from_state(state: dict[str, Any]) -> tuple[str, ...]:
    stored_prefixes = state.get("plot_features_recording_ignored_prefixes")
    if isinstance(stored_prefixes, list):
        return _normalized_prefixes(stored_prefixes)

    config_data = state.get("plot_features_config")
    if isinstance(config_data, dict):
        selected_recordings = config_data.get("selected_recordings")
        if isinstance(selected_recordings, list) and selected_recordings:
            return recording_ignored_prefixes_from_recordings(selected_recordings)

    recording_labels = _recording_labels_from_state(state)
    if recording_labels and not any(_entity_value_from_text(label, _SESSION_PREFIX) for label in recording_labels):
        return (_SESSION_PREFIX,)

    return ()


def _recording_labels_from_state(state: dict[str, Any]) -> list[str]:
    labels = []
    for key in ("plot_features_recordings", "plot_selected_recordings"):
        values = state.get(key)
        if isinstance(values, list):
            labels.extend(str(value) for value in values)

    groups = state.get("groups")
    if isinstance(groups, dict):
        for group in groups.values():
            if not isinstance(group, dict):
                continue
            files = group.get("files")
            if isinstance(files, list):
                labels.extend(str(value) for value in files)
    return labels


def _normalized_prefixes(prefixes: Iterable[Any]) -> tuple[str, ...]:
    normalized = []
    for prefix in prefixes:
        text = str(prefix).strip().lower().removesuffix("-")
        if text and text not in normalized:
            normalized.append(text)
    return tuple(normalized)


def _session_value(recording: Any) -> str:
    if isinstance(recording, dict):
        session = str(recording.get("session") or "").strip()
        if session:
            return session
        for key in ("relative_path", "path"):
            path_value = recording.get(key)
            if path_value:
                session = _entity_value_from_text(str(path_value), _SESSION_PREFIX)
                if session:
                    return session
        return ""

    return _entity_value_from_text(str(recording), _SESSION_PREFIX)


def _entity_value_from_text(value: str, entity_prefix: str) -> str:
    text = value.replace("\\", "/")
    prefix = f"{entity_prefix}-"
    for segment in text.split("/"):
        if segment.startswith(prefix) and "_" not in segment:
            return segment[len(prefix):]

    stem = _stem(value)
    for part in stem.split("_"):
        if part.startswith(prefix):
            return part[len(prefix):]
    return ""


def _stem(value: Any) -> str:
    text = str(value).replace("\\", "/")
    filename = text.rsplit("/", 1)[-1]
    if filename.lower().endswith(".tsv.gz"):
        return filename[:-7]
    return Path(filename).stem


__all__ = [
    "is_parameter_recording_file",
    "normalize_recording_base_id",
    "normalize_recording_id",
    "recording_ignored_prefixes_from_recordings",
    "recording_ignored_prefixes_from_state",
]
