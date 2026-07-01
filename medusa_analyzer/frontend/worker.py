import traceback
from collections.abc import Callable
from typing import Any
from PySide6.QtCore import QObject, QRunnable, Signal, Slot, QThreadPool


class WorkerSignals(QObject):
    """Señales que tendrá el worker. Son como canales de comunicación desde el hilo de fondo
    hacia la interfaz."""
    # Definimos una señal de progreso TIPO 'worker.signals.progress.emit(35)' que significa 'voy por 35%'.
    # Luego se conecta esa señal con la barra de progreso.
    progress = Signal(int)
    # Definimos una señal que manda el resultado final si toodo fue bien.
    result = Signal(object)
    error = Signal(str) # señal que manda texto de error si algo falla
    finished = Signal()


class Worker(QRunnable):
    def __init__(self, function: Callable[..., Any], *args, **kwargs):
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals() # guardamos las señales del worker

    @Slot()
    def run(self) -> None:
        try:
            self.kwargs["global_progress_callback"] = self.signals.progress.emit # vamos emitiendo progreso
            result_from_function = self.function(*self.args, **self.kwargs)
            self.signals.result.emit(result_from_function) # emitimos resultado de la función lanzada en 2º plano
        except Exception as exc:
            self.signals.error.emit(f"{exc}\n{traceback.format_exc()}") # emitimos error
        finally:
            self.signals.finished.emit() # emitimos señal de completado

class TaskRunner:
    def __init__(self):
        self.pool = QThreadPool.globalInstance()
        self._active: set[Worker] = set()

    def start(self, worker: Worker) -> None:
        self._active.add(worker)
        worker.signals.finished.connect(lambda: self._active.discard(worker))
        # Ejecutamos el worker en un hilo de fondo. Esto llama automáticamente a worker.run()
        self.pool.start(worker)
