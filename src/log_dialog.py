
from qtpy.QtWidgets import QDialog
from qtpy.QtGui import QTextCursor
from ui_log_dialog import Ui_LogDialog


class LogDialog(QDialog):
    def __init__(self, parent, title: str, log: str):
        super().__init__(parent)

        self.ui = Ui_LogDialog()
        self.ui.setupUi(self)

        self.setWindowTitle(title)
        self.ui.txt_log.setText(log)

        self.ui.txt_log.moveCursor(QTextCursor.End)
        self.ui.txt_log.moveCursor(QTextCursor.StartOfLine)

        