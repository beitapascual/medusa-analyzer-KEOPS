from PySide6.QtCore import QThreadPool

from .worker import Worker


class TaskRunner:
    def __init__(self):
        self.pool = QThreadPool.globalInstance()
        self._active: set[Worker] = set()

    def start(self, worker: Worker) -> None:
        self._active.add(worker)
        worker.signals.finished.connect(lambda: self._active.discard(worker))
        # Ejecutamos el worker en un hilo de fondo. Esto llama automáticamente a worker.run()
        self.pool.start(worker)
