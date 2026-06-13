import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    progress = Signal(int)
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class Worker(QRunnable):
    def __init__(self, function: Callable[..., Any], *args, **kwargs):
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.kwargs["progress_callback"] = self.signals.progress.emit
            self.signals.result.emit(self.function(*self.args, **self.kwargs))
        except Exception as exc:
            self.signals.error.emit(f"{exc}\n{traceback.format_exc()}")
        finally:
            self.signals.finished.emit()
