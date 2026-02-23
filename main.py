import sys
from PyQt6.QtWidgets import QApplication
from gui import FlowBench

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("FlowBench")
    window = FlowBench()
    window.show()
    sys.exit(app.exec())