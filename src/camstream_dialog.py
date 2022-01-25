
from PySide6.QtWidgets import QDialog, QMessageBox
from ui_camstream_dialog import Ui_CamstreamDialog
from util import settings_manager

class CamstreamDialog(QDialog):
    def __init__(self, parent = None) -> None:
        super().__init__(parent=parent)

        self.ui = Ui_CamstreamDialog()
        self.ui.setupUi(self)

        self.ui.buttonBox.accepted.connect(self.ok_clicked)
