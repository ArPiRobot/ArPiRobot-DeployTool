from typing import Dict, List

from qtpy.QtCore import QFile, QIODevice, QDir, QSettings, Qt
from qtpy.QtGui import QPalette, QColor
from qtpy.QtWidgets import  QApplication, QStyleFactory


WIFI_COUNTRY_CODES = ["AF", "AL", "DZ", "AS", "AD", "AO", "AI", "AQ", "AG", "AR", "AM", "AW", "AU", "AT", "AZ", "BS", "BH", "BD", "BB", "BY", "BE", "BZ", "BJ", "BM", "BT", "BO", "BQ", "BA", "BW", "BV", "BR", "IO", "BN", "BG", "BF", "BI", "KH", "CM", "CA", "CV", "KY", "CF", "TD", "CL", "CN", "CX", "CC", "CO", "KM", "CG", "CD", "CK", "CR", "CI", "HR", "CU", "CW", "CY", "CZ", "DK", "DJ", "DM", "DO", "EC", "EG", "SV", "GQ", "ER", "EE", "SZ", "ET", "FK", "FO", "FJ", "FI", "FR", "GF", "PF", "TF", "GA", "GM", "GE", "DE", "GH", "GI", "GR", "GL", "GD", "GP", "GU", "GT", "GG", "GN", "GW", "GY", "HT", "HM", "VA", "HN", "HK", "HU", "IS", "IN", "ID", "IR", "IQ", "IE", "IM", "IL", "IT", "JM", "JP", "JE", "JO", "KZ", "KE", "KI", "KP", "KR", "KW", "KG", "LA", "LV", "LB", "LS", "LR", "LY", "LI", "LT", "LU", "MO", "MG", "MW", "MY", "MV", "ML", "MT", "MH", "MQ", "MR", "MU", "YT", "MX", "FM", "MD", "MC", "MN", "ME", "MS", "MA", "MZ", "MM", "NA", "NR", "NP", "NL", "NC", "NZ", "NI", "NE", "NG", "NU", "NF", "MK", "MP", "NO", "OM", "PK", "PW", "PS", "PA", "PG", "PY", "PE", "PH", "PN", "PL", "PT", "PR", "QA", "RE", "RO", "RU", "RW", "BL", "SH", "KN", "LC", "MF", "PM", "VC", "WS", "SM", "ST", "SA", "SN", "RS", "SC", "SL", "SG", "SX", "SK", "SI", "SB", "SO", "ZA", "GS", "SS", "ES", "LK", "SD", "SR", "SJ", "SE", "CH", "SY", "TW", "TJ", "TZ", "TH", "TL", "TG", "TK", "TO", "TT", "TN", "TR", "TM", "TC", "TV", "UG", "UA", "AE", "GB", "UM", "US", "UY", "UZ", "VU", "VE", "VN", "VG", "VI", "WF", "EH", "YE", "ZM", "ZW", "AX"]


class ThemeManager:
    def __init__(self):
        self.system_theme = ""
        self.system_palette = None
        self.fusion_light_palette = None
        self.fusion_dark_palette = None
        self.default_font_size = 9
        self.app = None

    def set_app(self, app: QApplication):
        self.app = app
        
        self.system_theme = self.app.style().objectName()
        self.system_palette = self.app.palette()

        self.app.setStyle(QStyleFactory.create("Fusion"))
        
        self.fusion_light_palette = QPalette()
        self.fusion_light_palette.setColor(QPalette.Window, QColor.fromRgbF(0.937255, 0.937255, 0.937255, 1.000000))
        self.fusion_light_palette.setColor(QPalette.WindowText, QColor.fromRgbF(0.000000, 0.000000, 0.000000, 1.000000))
        self.fusion_light_palette.setColor(QPalette.Base, QColor.fromRgbF(1.000000, 1.000000, 1.000000, 1.000000))
        self.fusion_light_palette.setColor(QPalette.AlternateBase, QColor.fromRgbF(0.968627, 0.968627, 0.968627, 1.000000))
        self.fusion_light_palette.setColor(QPalette.ToolTipBase, QColor.fromRgbF(1.000000, 1.000000, 0.862745, 1.000000))
        self.fusion_light_palette.setColor(QPalette.ToolTipText, QColor.fromRgbF(0.000000, 0.000000, 0.000000, 1.000000))
        self.fusion_light_palette.setColor(QPalette.Text, QColor.fromRgbF(0.000000, 0.000000, 0.000000, 1.000000))
        self.fusion_light_palette.setColor(QPalette.Button, QColor.fromRgbF(0.937255, 0.937255, 0.937255, 1.000000))
        self.fusion_light_palette.setColor(QPalette.ButtonText, QColor.fromRgbF(0.000000, 0.000000, 0.000000, 1.000000))
        self.fusion_light_palette.setColor(QPalette.Link, QColor.fromRgbF(0.000000, 0.000000, 1.000000, 1.000000))
        self.fusion_light_palette.setColor(QPalette.Highlight, QColor.fromRgbF(0.188235, 0.549020, 0.776471, 1.000000))
        self.fusion_light_palette.setColor(QPalette.HighlightedText, QColor.fromRgbF(1.000000, 1.000000, 1.000000, 1.000000))
        self.fusion_light_palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor.fromRgbF(0.745098, 0.745098, 0.745098, 1.000000))
        self.fusion_light_palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor.fromRgbF(0.745098, 0.745098, 0.745098, 1.000000))
        self.fusion_light_palette.setColor(QPalette.Disabled, QPalette.Text, QColor.fromRgbF(0.745098, 0.745098, 0.745098, 1.000000))
        self.fusion_light_palette.setColor(QPalette.Disabled, QPalette.Light, QColor.fromRgbF(1.000000, 1.000000, 1.000000, 1.000000))

        self.fusion_dark_palette = QPalette()
        self.fusion_dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
        self.fusion_dark_palette.setColor(QPalette.WindowText, Qt.white)
        self.fusion_dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
        self.fusion_dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        self.fusion_dark_palette.setColor(QPalette.ToolTipBase, QColor(42, 130, 218))
        self.fusion_dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        self.fusion_dark_palette.setColor(QPalette.Text, Qt.white)
        self.fusion_dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        self.fusion_dark_palette.setColor(QPalette.ButtonText, Qt.white)
        self.fusion_dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        self.fusion_dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        self.fusion_dark_palette.setColor(QPalette.HighlightedText, Qt.black)
        self.fusion_dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(128, 128, 128))
        self.fusion_dark_palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(128, 128, 128))
        self.fusion_dark_palette.setColor(QPalette.Disabled, QPalette.Text, QColor(128, 128, 128))
        self.fusion_dark_palette.setColor(QPalette.Disabled, QPalette.Light, QColor(53, 53, 53))
    
    @property
    def themes(self) -> List[str]:
        return [
            "Custom Light",
            "Custom Dark",
            "Fusion Light",
            "Fusion Dark",
            "System"
        ]
    
    def apply_theme(self, theme: str, larger_fonts: bool):
        base_theme = ""
        stylesheet = ""
        palette = QPalette()
        if theme == "Custom Light" or theme == "Custom Dark":
            # Use default fusion palette with this theme
            palette = self.fusion_light_palette

            # Load stylesheet
            stylesheet_file = QFile(":/custom-theme/stylesheet.qss")
            if stylesheet_file.open(QIODevice.ReadOnly):
                stylesheet = bytes(stylesheet_file.readAll()).decode()
                stylesheet_file.close()
            
            # Make substitutions from csv file to use correct variant
            vars_file = QFile(":/custom-theme/{0}.csv".format("Light" if theme == "Custom Light" else "Dark"))
            if vars_file.open(QIODevice.ReadOnly):
                for line in bytes(vars_file.readAll()).decode().splitlines(False):
                    # Index 0 = variable, Index 1 = value
                    parts = line.replace(", ", ",").split(",")
                    stylesheet = stylesheet.replace("@{0}@".format(parts[0]), parts[1])
                vars_file.close()
            base_theme = "Fusion"
        elif theme == "Fusion Light":
            base_theme = "Fusion"
            stylesheet = ""
            palette = self.fusion_light_palette
        elif theme == "Fusion Dark":
            base_theme = "Fusion"
            palette = self.fusion_dark_palette
        else:
            base_theme = self.system_theme
            stylesheet = ""
            palette = self.system_palette
        
        # Apply theme
        self.app.setStyle(base_theme)
        self.app.setStyleSheet(stylesheet)
        self.app.setPalette(palette)

        # Support larger fonts
        size = 11 if larger_fonts else 9
        self.app.setStyleSheet("{0}\n{1}".format(self.app.styleSheet(), "*{{font-size: {0}pt}}".format(size)))

class SettingsManager:
    """
    Thin wrapper over QSettings object to manage deploy tool settings
    """
    def __init__(self):
        # Constants
        self.__SETTING_FILE = QDir.homePath() + "/.arpirobot/deploytool.ini"

        self.__ROBOT_IP_KEY = "robot-address"
        self.__ROBOT_USER_KEY = "robot-user"
        self.__THEME_KEY = "theme"
        self.__LARGE_FONTS_KEY = "larger-fonts"
        self.__LONG_TIMEOUTS_KEY = "longer-timeouts"
        self.__LAST_PROJ_FOLDER_KEY = "proj-folder"

        self.__DEFAULT_ROBOT_IP = "192.168.10.1"
        self.__DEFAULT_USER = "pi"
        self.__DEFAULT_THEME = "Custom Light"
        self.__DEFAULT_LARGE_FONTS = False
        self.__DEFAULT_LONG_TIMEOUT = False
        self.__DEFAULT_PROJ_FOLDER = ""

        # Setup
        self.__settings = QSettings(self.__SETTING_FILE, QSettings.IniFormat)

        # Setup defaults if settings are missing
        if self.__settings.value(self.__ROBOT_IP_KEY, None) is None:
            self.__settings.setValue(self.__ROBOT_IP_KEY, self.__DEFAULT_ROBOT_IP)
        if self.__settings.value(self.__ROBOT_USER_KEY, None) is None:
            self.__settings.setValue(self.__ROBOT_USER_KEY, self.__DEFAULT_USER)
        if self.__settings.value(self.__THEME_KEY, None) is None:
            self.__settings.setValue(self.__THEME_KEY, self.__DEFAULT_THEME)
        if self.__settings.value(self.__LARGE_FONTS_KEY, None) is None:
            self.__settings.setValue(self.__LARGE_FONTS_KEY, self.__DEFAULT_LARGE_FONTS)
        if self.__settings.value(self.__LONG_TIMEOUTS_KEY, None) is None:
            self.__settings.setValue(self.__LONG_TIMEOUTS_KEY, self.__DEFAULT_LONG_TIMEOUT)
        if self.__settings.value(self.__LAST_PROJ_FOLDER_KEY, None) is None:
            self.__settings.setValue(self.__LAST_PROJ_FOLDER_KEY, self.__DEFAULT_PROJ_FOLDER)

    @property
    def robot_address(self) -> str:
        return self.__settings.value(self.__ROBOT_IP_KEY, self.__DEFAULT_ROBOT_IP)

    @robot_address.setter
    def robot_address(self, value: str):
        self.__settings.setValue(self.__ROBOT_IP_KEY, value)

    @property
    def robot_user(self) -> str:
        return self.__settings.value(self.__ROBOT_USER_KEY, self.__DEFAULT_USER)
    
    @robot_user.setter
    def robot_user(self, value: str):
        self.__settings.setValue(self.__ROBOT_USER_KEY, value)

    @property
    def theme(self) -> str:
        return self.__settings.value(self.__THEME_KEY, self.__DEFAULT_THEME)

    @theme.setter
    def theme(self, value: str):
        self.__settings.setValue(self.__THEME_KEY, value)

    @property
    def larger_fonts(self) -> bool:
        return str(self.__settings.value(self.__LARGE_FONTS_KEY, self.__DEFAULT_LARGE_FONTS)).lower() == "true"

    @larger_fonts.setter
    def larger_fonts(self, value: bool):
        self.__settings.setValue(self.__LARGE_FONTS_KEY, value)
    
    @property
    def longer_timeouts(self) -> bool:
        return str(self.__settings.value(self.__LONG_TIMEOUTS_KEY, self.__DEFAULT_LONG_TIMEOUT)).lower() == "true"
    
    @longer_timeouts.setter
    def longer_timeouts(self, value: bool):
        self.__settings.setValue(self.__LONG_TIMEOUTS_KEY, value)
    
    @property
    def last_proj_folder(self) -> str:
        return self.__settings.value(self.__LAST_PROJ_FOLDER_KEY, self.__DEFAULT_PROJ_FOLDER)
    
    @last_proj_folder.setter
    def last_proj_folder(self, value: str):
        self.__settings.setValue(self.__LAST_PROJ_FOLDER_KEY, value)


theme_manager: ThemeManager = ThemeManager()
settings_manager: SettingsManager = SettingsManager()
