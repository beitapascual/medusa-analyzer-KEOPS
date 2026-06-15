import time
from collections.abc import Callable

from medusa_analyzer.backend.workflows.eeg_state import RecordingMetadata


# TODO: hacer que esta función permita cargar datos de cualquier tipo de experimento
# TODO: en función de la key del experimento. Sin es eeg, accedera a la carpeta eeg/ que hay
# TODO: en formato BIDS.
# TODO: que compruebe coherencia entre archivos

def load_recordings(
    paths: list[str], progress_callback: Callable[[int], None] | None = None
) -> RecordingMetadata:
    if not paths:
        raise ValueError("Select at least one recording.")
    for progress in range(0, 101, 10): # TODO: que no simule el progreso y lo haga real
        time.sleep(0.045)
        if progress_callback:
            progress_callback(progress)
    return RecordingMetadata( # Datos mock -- luego tendrá que leer datos reales
        n_files=len(paths), fs=1000.0, nyquist=500.0, n_channels=32,
        duration_seconds=120.0, frequency_range=(0.0, 500.0))
