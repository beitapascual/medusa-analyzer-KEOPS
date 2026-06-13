from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


class StepProgressBar(QWidget):
    STATES = {"locked", "active", "completed", "error"}

    def __init__(self, labels: list[str]):
        super().__init__()
        self.labels = labels
        self.states = ["active"] + ["locked"] * (len(labels) - 1)
        self.setMinimumHeight(92)
        self.setProperty("role", "step-progress")

    def set_states(self, states: list[str]) -> None:
        if len(states) != len(self.labels) or any(state not in self.STATES for state in states):
            raise ValueError("Invalid step states.")
        self.states = states
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        margin, y = 72, 30
        width = max(1, self.width() - margin * 2)
        spacing = width / max(1, len(self.labels) - 1)
        colors = {
            "locked": QColor("#C9C4C7"), "active": QColor("#8A1538"),
            "completed": QColor("#8A1538"), "error": QColor("#C85663"),
        }
        painter.setPen(QPen(QColor("#DDD7D8"), 3))
        painter.drawLine(margin, y, self.width() - margin, y)
        font = QFont()
        font.setBold(True)
        for index, (label, state) in enumerate(zip(self.labels, self.states)):
            x = int(margin + spacing * index)
            painter.setBrush(colors[state])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(x - 16, y - 16, 32, 32)
            painter.setFont(font)
            painter.setPen(QColor("white"))
            painter.drawText(x - 16, y - 16, 32, 32, Qt.AlignmentFlag.AlignCenter, str(index + 1))
            painter.setPen(QColor("#1E1E24") if state != "locked" else QColor("#8D878E"))
            painter.drawText(x - 68, y + 24, 136, 28, Qt.AlignmentFlag.AlignHCenter, label)
