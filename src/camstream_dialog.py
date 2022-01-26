
from PySide6.QtWidgets import QDialog, QMessageBox
from PySide6.QtGui import QIntValidator, QDoubleValidator, QRegularExpressionValidator
from ui_camstream_dialog import Ui_CamstreamDialog
from util import settings_manager
import re

class CamstreamDialog(QDialog):
    def __init__(self, parent = None) -> None:
        super().__init__(parent=parent)

        self.ui = Ui_CamstreamDialog()
        self.ui.setupUi(self)

        self.ui.txt_width.setValidator(QIntValidator(0, 7680, self))
        self.ui.txt_height.setValidator(QIntValidator(0, 4320, self))
        self.ui.txt_framerate.setValidator(QIntValidator(0, 360, self))
        self.ui.txt_gain.setValidator(QDoubleValidator(0.0, 100.0, 2, self))
        self.ui.txt_bitrate.setValidator(QRegularExpressionValidator(r"[0-9]*", self))
        self.ui.txt_quality.setValidator(QIntValidator(0, 100, self))
        self.ui.txt_port.setValidator(QIntValidator(0, 65535, self))

    def accept(self):
        if self.ui.txt_config_name.text() == "":
            dialog = QMessageBox(parent=self)
            dialog.setIcon(QMessageBox.Warning)
            dialog.setText(self.tr("Name the config before saving."))
            dialog.setWindowTitle(self.tr("Configuration not Named"))
            dialog.setStandardButtons(QMessageBox.Ok)
            dialog.exec()
        else:
            return super().accept()
    
    def from_config(self, config: str):
        # Parse a config file and populate the UI from it
        pass

    def to_config(self) -> str:
        # Converts the settings from the UI into a config file for the ArPiRobot-Camstream service
        flip_txt = self.ui.combox_flip.currentText()
        vflip = flip_txt == self.tr("Vertical") or flip_txt == self.tr("Both")
        hflip = flip_txt == self.tr("Horizontal") or flip_txt == self.tr("Both")
        config = (
            "--driver {driver}\n"
            "--device {device}\n"
            "--iomode {iomode}\n"
            "--width {width}\n"
            "--height {height}\n"
            "--framerate {framerate}\n"
            "{vflip}\n"
            "{hflip}\n"
            "--rotate {rotation}\n"
            "--gain {gain}\n"
            "--format {format}\n"
            "--h264encoder {encoder}\n"
            "--profile {profile}\n"
            "--bitrate {bitrate}\n"
            "--quality {quality}\n"
            "--netmode {netmode}\n"
            "--address {address}\n"
            "--port {port}\n"
            "--rtspkey {rtspkey}\n"
        ).format(
            driver = self.ui.combox_driver.currentText(),
            device = self.ui.txt_device.text(),
            iomode = self.ui.combox_iomode.currentText(),
            width = self.ui.txt_width.text(),
            height = self.ui.txt_height.text(),
            framerate = self.ui.txt_framerate.text(),
            vflip = "--vflip" if vflip else "",
            hflip = "--hflip" if hflip else "",
            rotation = self.ui.combox_rotate.currentText().replace("°", ""),
            gain = self.ui.txt_gain.text(),
            format = self.ui.combox_format.currentText(),
            encoder = self.ui.combox_encoder.currentText(),
            profile = self.ui.combox_profile.currentText(),
            bitrate = self.ui.txt_bitrate.text(),
            quality = self.ui.txt_quality.text(),
            netmode = self.ui.combox_netmode.currentText(),
            address = self.ui.txt_address.text(),
            port = self.ui.txt_port.text(),
            rtspkey = self.ui.txt_rtspkey.text()
        )

        # Remove blank lines
        return re.sub(r"(?<=\n)\s+", "", config, re.MULTILINE)

