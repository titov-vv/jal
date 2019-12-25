import sys
from PySide2.QtWidgets import QApplication
from main_window import MainWindow

if __name__ == "__main__":
    app = QApplication([])

    window = MainWindow()
    #window.showMaximized()
    window.show()

    sys.exit(app.exec_())
