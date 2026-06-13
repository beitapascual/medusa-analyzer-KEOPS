"""Generate a small, standards-compliant EDF recording for manual testing."""

from __future__ import annotations

import math
import struct
from pathlib import Path


CHANNELS = ("Fp1", "Fp2", "C3", "C4")
SAMPLE_RATE = 100
RECORD_SECONDS = 1
N_RECORDS = 10
DIGITAL_MIN = -32768
DIGITAL_MAX = 32767
PHYSICAL_MIN = -200.0
PHYSICAL_MAX = 200.0


def field(value: object, width: int) -> bytes:
    encoded = str(value).encode("ascii")
    if len(encoded) > width:
        raise ValueError(f"{value!r} does not fit in an EDF field of width {width}")
    return encoded.ljust(width, b" ")


def repeated(values: list[object], width: int) -> bytes:
    return b"".join(field(value, width) for value in values)


def physical_to_digital(value: float) -> int:
    normalized = (value - PHYSICAL_MIN) / (PHYSICAL_MAX - PHYSICAL_MIN)
    digital = DIGITAL_MIN + normalized * (DIGITAL_MAX - DIGITAL_MIN)
    return max(DIGITAL_MIN, min(DIGITAL_MAX, round(digital)))


def build_header() -> bytes:
    signal_count = len(CHANNELS)
    header_bytes = 256 + signal_count * 256
    header = b"".join(
        (
            field("0", 8),
            field("FAKE-EEG M 01-JAN-1990", 80),
            field("Startdate 12-JUN-2026 Medusa Analyzer", 80),
            field("12.06.26", 8),
            field("12.00.00", 8),
            field(header_bytes, 8),
            field("", 44),
            field(N_RECORDS, 8),
            field(RECORD_SECONDS, 8),
            field(signal_count, 4),
            repeated(list(CHANNELS), 16),
            repeated(["Synthetic EEG"] * signal_count, 80),
            repeated(["uV"] * signal_count, 8),
            repeated([PHYSICAL_MIN] * signal_count, 8),
            repeated([PHYSICAL_MAX] * signal_count, 8),
            repeated([DIGITAL_MIN] * signal_count, 8),
            repeated([DIGITAL_MAX] * signal_count, 8),
            repeated(["HP:0.5Hz LP:40Hz"] * signal_count, 80),
            repeated([SAMPLE_RATE * RECORD_SECONDS] * signal_count, 8),
            repeated([""] * signal_count, 32),
        )
    )
    if len(header) != header_bytes:
        raise AssertionError(f"Invalid EDF header size: {len(header)} != {header_bytes}")
    return header


def build_data() -> bytes:
    data = bytearray()
    samples_per_record = SAMPLE_RATE * RECORD_SECONDS
    frequencies = (10.0, 11.0, 8.0, 12.0)
    phases = (0.0, 0.4, 0.8, 1.2)

    for record in range(N_RECORDS):
        for frequency, phase in zip(frequencies, phases):
            for sample in range(samples_per_record):
                time = record * RECORD_SECONDS + sample / SAMPLE_RATE
                signal = (
                    45.0 * math.sin(2.0 * math.pi * frequency * time + phase)
                    + 12.0 * math.sin(2.0 * math.pi * 2.0 * time)
                    + 3.0 * math.sin(2.0 * math.pi * 50.0 * time)
                )
                data.extend(struct.pack("<h", physical_to_digital(signal)))
    return bytes(data)


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "sample_data" / "fake_eeg_recording.edf"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(build_header() + build_data())
    print(output)


if __name__ == "__main__":
    main()
