from pathlib import Path

from PySide6.QtCore import (Property, QEasingCurve, QEvent, QPropertyAnimation,
    QRectF, Qt, Signal)
from PySide6.QtGui import (QColor, QCursor, QKeyEvent, QMouseEvent, QPainter,
    QPainterPath, QPixmap)
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
    QLabel, QSizePolicy, QVBoxLayout, QWidget)

class ExperimentCard(QWidget):
    """Vertical, keyboard-accessible module card used by the dashboard."""

    clicked = Signal()

    def __init__(self, title: str, subtitle: str, icon_path: Path | None, enabled: bool = True,
        status: str = "", accent: str = "burgundy"):
        super().__init__()
        self._hover_progress = 0.0
        self._enabled = enabled
        self.setObjectName("moduleCardShell")
        self.setProperty("role", "module-card-shell")
        self.setProperty("enabled", enabled)
        self.setProperty("accent", accent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus if enabled else Qt.FocusPolicy.NoFocus)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor))
        self.setAccessibleName(f"{title}. {subtitle.rstrip('.')}." + (f" {status}" if status else ""))
        self.setAccessibleDescription("Open this experiment workflow." if enabled else "This module is coming soon.")
        self.setToolTip(f"Open {title}" if enabled else f"{title} is coming soon")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(304, 344)

        self.surface = QFrame(self)
        self.surface.setObjectName("moduleCard")
        self.surface.setProperty("role", "module-card")
        self.surface.setProperty("enabled", enabled)
        self.surface.setProperty("accent", accent)
        self.surface.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.shadow = QGraphicsDropShadowEffect(self.surface)
        self.shadow.setBlurRadius(25)
        self.shadow.setOffset(0, 7)
        self.shadow.setColor(QColor(54, 30, 39, 36))
        self.surface.setGraphicsEffect(self.shadow)

        root = QVBoxLayout(self.surface)
        root.setContentsMargins(30, 24, 30, 27)
        root.setSpacing(0)

        badge_row = QHBoxLayout()
        badge_row.addStretch()
        badge = QLabel(status or ("Available" if enabled else "Coming soon"))
        badge.setObjectName("moduleBadge")
        badge.setProperty("status", "ready" if enabled else "soon")
        badge_row.addWidget(badge)
        root.addLayout(badge_row)
        root.addSpacing(13)

        icon = QLabel()
        icon.setObjectName("moduleIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(126, 126)
        if icon_path is not None and icon_path.is_file():
            pixmap = QPixmap(str(icon_path))
            crop_size = int(min(pixmap.width(), pixmap.height()) * 0.76)
            crop = pixmap.copy((pixmap.width() - crop_size) // 2, (pixmap.height() - crop_size) // 2, crop_size, crop_size)
            scaled = crop.scaled(106, 106, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            clipped = QPixmap(106, 106)
            clipped.fill(Qt.GlobalColor.transparent)
            painter = QPainter(clipped)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            path = QPainterPath()
            path.addEllipse(QRectF(0, 0, 106, 106))
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, scaled)
            painter.end()
            icon.setPixmap(clipped)
        else:
            icon.setText(title)
        root.addWidget(icon, alignment=Qt.AlignmentFlag.AlignHCenter)
        root.addSpacing(15)

        title_label = QLabel(title)
        title_label.setObjectName("moduleTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title_label)
        root.addSpacing(9)

        accent_line = QFrame()
        accent_line.setObjectName("moduleAccent")
        accent_line.setFixedSize(48, 3)
        root.addWidget(accent_line, alignment=Qt.AlignmentFlag.AlignHCenter)
        root.addSpacing(13)

        description = QLabel(subtitle)
        description.setObjectName("moduleDescription")
        description.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        description.setWordWrap(True)
        description.setFixedHeight(42)
        root.addWidget(description)
        root.addStretch()

        hint = QLabel("OPEN GUIDED PIPELINE" if enabled else "NOT YET AVAILABLE")
        hint.setObjectName("moduleHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(hint)

        self.animation = QPropertyAnimation(self, b"hoverProgress", self)
        self.animation.setDuration(180)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._position_surface()

    def set_card_width(self, width: int) -> None:
        self.setFixedWidth(width)
        self._position_surface()

    def _position_surface(self) -> None:
        lift = round(self._hover_progress * 4)
        self.surface.setGeometry(8, 10 - lift, max(0, self.width() - 16), 322)

    def get_hover_progress(self) -> float:
        return self._hover_progress

    def set_hover_progress(self, value: float) -> None:
        self._hover_progress = value
        self._position_surface()
        self.shadow.setBlurRadius(25 + 11 * value)
        self.shadow.setOffset(0, 7 - 2 * value)

    hoverProgress = Property(float, get_hover_progress, set_hover_progress)

    def _animate_to(self, target: float) -> None:
        if not self._enabled:
            return
        self.animation.stop()
        self.animation.setStartValue(self._hover_progress)
        self.animation.setEndValue(target)
        self.animation.start()
        active = target > 0
        self.surface.setProperty("hovered", active)
        self._refresh_surface_style()

    def _refresh_surface_style(self) -> None:
        self.surface.style().unpolish(self.surface)
        self.surface.style().polish(self.surface)

    def enterEvent(self, event: QEvent) -> None:
        self._animate_to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self._animate_to(0.0)
        super().leaveEvent(event)

    def focusInEvent(self, event) -> None:
        self.surface.setProperty("focused", True)
        self._refresh_surface_style()
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        self.surface.setProperty("focused", False)
        self._refresh_surface_style()
        super().focusOutEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._enabled and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit() # Emitimos señal de que se ha clicado en la tarjeta para que lo reciba el dashboard
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._enabled and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit() # Emitimos señal de que se ha clicado en la tarjeta para que lo reciba el dashboard
            event.accept()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:
        self._position_surface()
        super().resizeEvent(event)
