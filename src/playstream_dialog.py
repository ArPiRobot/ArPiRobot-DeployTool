from typing import Optional
from ui_playstream_dialog import Ui_PlayStreamDialog
from qtpy.QtWidgets import QDialog, QWidget
from qtpy.QtCore import QTimer, Qt
from qtpy.QtGui import QCloseEvent
import subprocess
import signal


class PlayStreamDialog(QDialog):
    def __init__(self, title: str, message: str, proc: subprocess.Popen, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.Tool)

        self.proc = proc

        self.ui = Ui_PlayStreamDialog()
        self.ui.setupUi(self)

        self.timer = QTimer()
        self.timer.timeout.connect(self.poll_proc)
    
        self.setWindowTitle(title)
        self.ui.lbl_message.setText(message)

        self.timer.start(500)
    
    def poll_proc(self):
        if self.proc.poll() is not None:
            self.close()

    def closeEvent(self, arg__1: QCloseEvent):
        self.proc.kill()
    
    def reject(self):
        self.proc.kill()
    
    def accept(self):
        self.proc.kill()
