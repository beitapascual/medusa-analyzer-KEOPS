from PySide6.QtCore import Property, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


# Barra de progreso visual de los pasos del workflow
class StepProgressBar(QWidget):
    STATES = {"locked", "active", "completed", "error"} # estados válidos de un paso

    # El constructor recibe una lsita de nombres de pasos
    def __init__(self, labels: list[str]):
        super().__init__()
        self.labels = labels
        # Inicializamos los estados. Al principio, el primer estado está activo y los demás bloqueados.
        self.states = ["active"] + ["locked"] * (len(labels) - 1)
        self._line_color = QColor("#DDD7D8")
        self._locked_step_color = QColor("#C9C4C7")
        self._active_step_color = QColor("#8A1538")
        self._completed_step_color = QColor("#8A1538")
        self._error_step_color = QColor("#C85663")
        self._number_color = QColor("white")
        self._locked_label_color = QColor("white")
        self._active_label_color = QColor("#E35A82")
        self._completed_label_color = QColor("white")
        self._error_label_color = QColor("white") # TODO: si el fondo es claro no se ve
        self.setMinimumHeight(92)
        self.setProperty("role", "step-progress")

    def set_states(self, states: list[str]) -> None:
        """Se llama desde WorkflowShell y sirve para actualizar qué pasos están completed, active o locked."""
        if len(states) != len(self.labels) or any(state not in self.STATES for state in states):
            # Valida que haya tantos estados como labels, que todos los estados sean válidos.
            raise ValueError("Invalid step states.")
        self.states = states # guardamos los nuevos estados
        self.update() # volvemos a pintar

    def _set_color(self, attribute: str, value) -> None:
        """Métoodo auxiliar para cambiar un color interno"""
        setattr(self, attribute, QColor(value))
        self.update()

    def _step_color(self, state: str) -> QColor:
        """devuelve el color del círculo según el estado."""
        colors = {"locked": self._locked_step_color, "active": self._active_step_color,
            "completed": self._completed_step_color, "error": self._error_step_color}
        return colors[state]

    def _label_color(self, state: str) -> QColor:
        colors = {"locked": self._locked_label_color, "active": self._active_label_color,
            "completed": self._completed_label_color, "error": self._error_label_color}
        return colors[state]

    def get_line_color(self) -> QColor:
        return self._line_color

    def set_line_color(self, value) -> None:
        self._set_color("_line_color", value)

    def get_locked_step_color(self) -> QColor:
        return self._locked_step_color

    def set_locked_step_color(self, value) -> None:
        self._set_color("_locked_step_color", value)

    def get_active_step_color(self) -> QColor:
        return self._active_step_color

    def set_active_step_color(self, value) -> None:
        self._set_color("_active_step_color", value)

    def get_completed_step_color(self) -> QColor:
        return self._completed_step_color

    def set_completed_step_color(self, value) -> None:
        self._set_color("_completed_step_color", value)

    def get_error_step_color(self) -> QColor:
        return self._error_step_color

    def set_error_step_color(self, value) -> None:
        self._set_color("_error_step_color", value)

    def get_number_color(self) -> QColor:
        return self._number_color

    def set_number_color(self, value) -> None:
        self._set_color("_number_color", value)

    def get_locked_label_color(self) -> QColor:
        return self._locked_label_color

    def set_locked_label_color(self, value) -> None:
        self._set_color("_locked_label_color", value)

    def get_active_label_color(self) -> QColor:
        return self._active_label_color

    def set_active_label_color(self, value) -> None:
        self._set_color("_active_label_color", value)

    def get_completed_label_color(self) -> QColor:
        return self._completed_label_color

    def set_completed_label_color(self, value) -> None:
        self._set_color("_completed_label_color", value)

    def get_error_label_color(self) -> QColor:
        return self._error_label_color

    def set_error_label_color(self, value) -> None:
        self._set_color("_error_label_color", value)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        margin, y = 72, 30
        width = max(1, self.width() - margin * 2)
        spacing = width / max(1, len(self.labels) - 1)
        painter.setPen(QPen(self._line_color, 3))
        painter.drawLine(margin, y, self.width() - margin, y)
        font = QFont()
        font.setBold(True)
        for index, (label, state) in enumerate(zip(self.labels, self.states)):
            x = int(margin + spacing * index)
            painter.setBrush(self._step_color(state))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(x - 16, y - 16, 32, 32)
            painter.setFont(font)
            painter.setPen(self._number_color)
            painter.drawText(x - 16, y - 16, 32, 32, Qt.AlignmentFlag.AlignCenter, str(index + 1))
            painter.setPen(self._label_color(state))
            painter.drawText(x - 68, y + 24, 136, 28, Qt.AlignmentFlag.AlignHCenter, label)

    lineColor = Property(QColor, get_line_color, set_line_color)
    lockedStepColor = Property(QColor, get_locked_step_color, set_locked_step_color)
    activeStepColor = Property(QColor, get_active_step_color, set_active_step_color)
    completedStepColor = Property(QColor, get_completed_step_color, set_completed_step_color)
    errorStepColor = Property(QColor, get_error_step_color, set_error_step_color)
    numberColor = Property(QColor, get_number_color, set_number_color)
    lockedLabelColor = Property(QColor, get_locked_label_color, set_locked_label_color)
    activeLabelColor = Property(QColor, get_active_label_color, set_active_label_color)
    completedLabelColor = Property(QColor, get_completed_label_color, set_completed_label_color)
    errorLabelColor = Property(QColor, get_error_label_color, set_error_label_color)
