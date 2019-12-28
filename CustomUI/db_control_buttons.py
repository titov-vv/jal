from PySide2.QtWidgets import QWidget, QHBoxLayout, QPushButton

class DbControlButtons(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        self.layout = QHBoxLayout()
        self.layout.setMargin(0)
        self.add_button = QPushButton("Add")
        self.layout.addWidget(self.add_button)
        self.del_button = QPushButton("Del")
        self.layout.addWidget(self.del_button)
        self.copy_button = QPushButton("Copy")
        self.layout.addWidget(self.copy_button)
        self.commit_button = QPushButton("Commit")
        self.layout.addWidget(self.commit_button)
        self.setLayout(self.layout)