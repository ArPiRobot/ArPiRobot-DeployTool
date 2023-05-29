
from PySide6.QtWidgets import QDialog
from ui_settings_dialog import Ui_SettingsDialog
from util import settings_manager


class SettingsDialog(QDialog):
    def __init__(self, parent = None) -> None:
        super().__init__(parent=parent)

        self.ui = Ui_SettingsDialog()
        self.ui.setupUi(self)

        self.ui.chbox_larger_font.setChecked(settings_manager.larger_fonts)

    def save_settings(self):
        settings_manager.larger_fonts = self.ui.chbox_larger_font.isChecked()
