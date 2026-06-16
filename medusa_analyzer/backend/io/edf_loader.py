from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np


def _read_ascii(block: bytes) -> str:
    return block.decode("ascii", errors="ignore").strip()


def _read_int(block: bytes) -> int:
    text = _read_ascii(block)
    return int(text) if text else 0


def _read_float(block: bytes) -> float | None:
    text = _read_ascii(block)
    return float(text) if text else None


def _read_repeated_strings(payload: bytes, offset: int, count: int, width: int) -> tuple[list[str], int]:
    values = [_read_ascii(payload[offset + index * width: offset + (index + 1) * width])
        for index in range(count)]
    return values, offset + count * width


def _read_repeated_ints(payload: bytes, offset: int, count: int, width: int) -> tuple[list[int], int]:
    values = [_read_int(payload[offset + index * width: offset + (index + 1) * width])
        for index in range(count)]
    return values, offset + count * width


def _read_repeated_floats(payload: bytes, offset: int, count: int, width: int) -> tuple[list[float | None], int]:
    values = [_read_float(payload[offset + index * width: offset + (index + 1) * width]) for index in range(count)]
    return values, offset + count * width


def _physical_scale(digital_values: np.ndarray, physical_min: float | None, physical_max: float | None,
    digital_min: int, digital_max: int) -> np.ndarray:
    if physical_min is None or physical_max is None:
        return digital_values.astype(np.float64, copy=False)
    denominator = digital_max - digital_min
    if denominator == 0:
        return digital_values.astype(np.float64, copy=False)
    scale = (physical_max - physical_min) / denominator
    return (digital_values - digital_min) * scale + physical_min


def load_edf_file(path: str | Path, progress_callback: Callable[[int], None] | None = None) -> dict:
    file_path = Path(path).expanduser().resolve()
    payload = file_path.read_bytes()
    if progress_callback:
        progress_callback(5)

    version = _read_ascii(payload[0:8])
    patient_id = _read_ascii(payload[8:88])
    recording_id = _read_ascii(payload[88:168])
    start_date = _read_ascii(payload[168:176])
    start_time = _read_ascii(payload[176:184])
    header_bytes = _read_int(payload[184:192])
    reserved = _read_ascii(payload[192:236])
    record_count = _read_int(payload[236:244])
    record_duration = _read_float(payload[244:252]) or 0.0
    signal_count = _read_int(payload[252:256])

    if progress_callback:
        progress_callback(15)

    offset = 256
    labels, offset = _read_repeated_strings(payload, offset, signal_count, 16)
    transducer_types, offset = _read_repeated_strings(payload, offset, signal_count, 80)
    physical_dimensions, offset = _read_repeated_strings(payload, offset, signal_count, 8)
    physical_mins, offset = _read_repeated_floats(payload, offset, signal_count, 8)
    physical_maxs, offset = _read_repeated_floats(payload, offset, signal_count, 8)
    digital_mins, offset = _read_repeated_ints(payload, offset, signal_count, 8)
    digital_maxs, offset = _read_repeated_ints(payload, offset, signal_count, 8)
    prefilterings, offset = _read_repeated_strings(payload, offset, signal_count, 80)
    samples_per_record, offset = _read_repeated_ints(payload, offset, signal_count, 8)
    reserved_signals, offset = _read_repeated_strings(payload, offset, signal_count, 32)

    bytes_per_record = sum(samples_per_record) * 2
    if record_count < 0 and bytes_per_record:
        record_count = max(0, (len(payload) - header_bytes) // bytes_per_record)

    if progress_callback:
        progress_callback(35)

    total_samples_per_channel = [samples * max(record_count, 0) for samples in samples_per_record]
    sampling_rates = [(samples / record_duration) if record_duration and samples else None
        for samples in samples_per_record]

    channel_arrays = [np.empty(total_samples, dtype=np.float64) for total_samples in total_samples_per_channel]
    positions = [0] * signal_count
    cursor = header_bytes

    for record_index in range(max(record_count, 0)):
        for signal_index, sample_count in enumerate(samples_per_record):
            byte_count = sample_count * 2
            chunk = payload[cursor: cursor + byte_count]
            cursor += byte_count
            digital_values = np.frombuffer(chunk, dtype="<i2").astype(np.float64)
            physical_values = _physical_scale(
                digital_values,
                physical_mins[signal_index],
                physical_maxs[signal_index],
                digital_mins[signal_index],
                digital_maxs[signal_index],
            )
            start = positions[signal_index]
            end = start + sample_count
            channel_arrays[signal_index][start:end] = physical_values
            positions[signal_index] = end
        if progress_callback and record_count:
            progress_callback(35 + int(55 * (record_index + 1) / record_count))

    data = (
        np.vstack(channel_arrays)
        if channel_arrays
        else np.empty((signal_count, 0), dtype=np.float64)
    )
    shared_sampling_rate = (
        sampling_rates[0]
        if sampling_rates and len(set(sampling_rates)) == 1
        else None
    )
    shared_sample_count = (
        total_samples_per_channel[0]
        if total_samples_per_channel and len(set(total_samples_per_channel)) == 1
        else None
    )
    duration_seconds = record_count * record_duration if record_duration else None

    signal_metadata = []
    for index, label in enumerate(labels):
        signal_metadata.append(
            {
                "label": label,
                "transducer": transducer_types[index],
                "physical_dimension": physical_dimensions[index],
                "physical_min": physical_mins[index],
                "physical_max": physical_maxs[index],
                "digital_min": digital_mins[index],
                "digital_max": digital_maxs[index],
                "prefiltering": prefilterings[index],
                "samples_per_record": samples_per_record[index],
                "sampling_rate": sampling_rates[index],
                "reserved": reserved_signals[index],
            }
        )

    if progress_callback:
        progress_callback(100)

    return {
        "path": str(file_path),
        "name": file_path.name,
        "version": version,
        "patient_id": patient_id,
        "recording_id": recording_id,
        "start_date": start_date,
        "start_time": start_time,
        "reserved": reserved,
        "header_bytes": header_bytes,
        "record_count": record_count,
        "record_duration_seconds": record_duration or None,
        "channels": labels,
        "n_channels": signal_count,
        "sampling_rate": shared_sampling_rate,
        "sampling_rates": sampling_rates,
        "duration_seconds": duration_seconds,
        "n_samples": shared_sample_count,
        "samples_per_channel": total_samples_per_channel,
        "data": data,
        "signal_metadata": signal_metadata,
    }
