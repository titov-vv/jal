import sys
from PySide2.QtWidgets import QApplication
from PySide2 import QtCore
from main_window import MainWindow

if __name__ == "__main__":
    app = QApplication([])
    font = app.font()
    font.setPixelSize(15)
    app.setFont(font)

    window = MainWindow()
    #window.showMaximized()
    window.show()

    sys.exit(app.exec_())
