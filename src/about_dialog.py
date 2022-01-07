from PySide6.QtCore import QFile
from PySide6.QtWidgets import QDialog
from ui_about_dialog import Ui_AboutDialog


class AboutDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.ui = Ui_AboutDialog()
        self.ui.setupUi(self)

        license_file = QFile(":/license_text.txt")
        if license_file.open(QFile.ReadOnly):
            self.ui.txt_license.setHtml(bytes(license_file.readAll()).decode())
        license_file.close()

        third_party_file = QFile(":/third_party_licenses.txt")
        if third_party_file.open(QFile.ReadOnly):
            self.ui.txt_third_party.setHtml(bytes(third_party_file.readAll()).decode())
        third_party_file.close()
