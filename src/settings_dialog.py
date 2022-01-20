
from PySide6.QtWidgets import QDialog
from ui_settings_dialog import Ui_SettingsDialog
from util import settings_manager


class SettingsDialog(QDialog):
    def __init__(self, parent = None) -> None:
        super().__init__(parent=parent)

        self.ui = Ui_SettingsDialog()
        self.ui.setupUi(self)

        # Manually create this list, so the order can be manually selected
        self.ui.combox_themes.addItems(["Light", "Dark"])
        self.ui.combox_themes.setCurrentText(settings_manager.theme)

        self.ui.chbox_larger_font.setChecked(settings_manager.larger_fonts)

    def save_settings(self):
        settings_manager.theme = self.ui.combox_themes.currentText()
        settings_manager.larger_fonts = self.ui.chbox_larger_font.isChecked()
