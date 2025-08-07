from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor

class QCollapsibleBox(QWidget):
    """A custom collapsible box widget"""
    
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        
        self.toggleButton = QPushButton(title)
        self.toggleButton.setStyleSheet("text-align: left; padding: 5px;")
        self.toggleButton.setCheckable(True)
        self.toggleButton.setChecked(True)
        self.toggleButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        self.contentWidget = QWidget()
        self.contentWidget.setVisible(True)
        
        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toggleButton)
        lay.addWidget(self.contentWidget)
        
        self.toggleButton.toggled.connect(self.toggle)
        
    def setContentLayout(self, layout):
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)
        self.contentWidget.setLayout(layout)
        
        self.toggleButton.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 4px;
                margin: 0px;
                border: none;
                background-color: #f0f0f0;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        
    def toggle(self, checked):
        self.contentWidget.setVisible(checked)
