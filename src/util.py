from typing import Dict, List

from PySide6.QtCore import QFile, QIODevice, QDir, QSettings, Qt
from PySide6.QtGui import QPalette, QColor, QFont
from PySide6.QtWidgets import  QApplication, QStyleFactory


WIFI_COUNTRY_CODES = ["AF", "AL", "DZ", "AS", "AD", "AO", "AI", "AQ", "AG", "AR", "AM", "AW", "AU", "AT", "AZ", "BS", "BH", "BD", "BB", "BY", "BE", "BZ", "BJ", "BM", "BT", "BO", "BQ", "BA", "BW", "BV", "BR", "IO", "BN", "BG", "BF", "BI", "KH", "CM", "CA", "CV", "KY", "CF", "TD", "CL", "CN", "CX", "CC", "CO", "KM", "CG", "CD", "CK", "CR", "CI", "HR", "CU", "CW", "CY", "CZ", "DK", "DJ", "DM", "DO", "EC", "EG", "SV", "GQ", "ER", "EE", "SZ", "ET", "FK", "FO", "FJ", "FI", "FR", "GF", "PF", "TF", "GA", "GM", "GE", "DE", "GH", "GI", "GR", "GL", "GD", "GP", "GU", "GT", "GG", "GN", "GW", "GY", "HT", "HM", "VA", "HN", "HK", "HU", "IS", "IN", "ID", "IR", "IQ", "IE", "IM", "IL", "IT", "JM", "JP", "JE", "JO", "KZ", "KE", "KI", "KP", "KR", "KW", "KG", "LA", "LV", "LB", "LS", "LR", "LY", "LI", "LT", "LU", "MO", "MG", "MW", "MY", "MV", "ML", "MT", "MH", "MQ", "MR", "MU", "YT", "MX", "FM", "MD", "MC", "MN", "ME", "MS", "MA", "MZ", "MM", "NA", "NR", "NP", "NL", "NC", "NZ", "NI", "NE", "NG", "NU", "NF", "MK", "MP", "NO", "OM", "PK", "PW", "PS", "PA", "PG", "PY", "PE", "PH", "PN", "PL", "PT", "PR", "QA", "RE", "RO", "RU", "RW", "BL", "SH", "KN", "LC", "MF", "PM", "VC", "WS", "SM", "ST", "SA", "SN", "RS", "SC", "SL", "SG", "SX", "SK", "SI", "SB", "SO", "ZA", "GS", "SS", "ES", "LK", "SD", "SR", "SJ", "SE", "CH", "SY", "TW", "TJ", "TZ", "TH", "TL", "TG", "TK", "TO", "TT", "TN", "TR", "TM", "TC", "TV", "UG", "UA", "AE", "GB", "UM", "US", "UY", "UZ", "VU", "VE", "VN", "VG", "VI", "WF", "EH", "YE", "ZM", "ZW", "AX"]


class ThemeManager:
    def __init__(self):
        self.system_theme = ""
        self.default_font_size: float = 9
        self.large_font_factor = 1.2
        self.app = None

    def set_app(self, app: QApplication):
        self.app = app
        self.system_theme = self.app.style().name()
        self.default_font_size = QFont().pointSizeF()
    
    @property
    def themes(self) -> List[str]:
        return [
            "System",
            "Fusion"
        ]
    
    def apply_theme(self, theme: str, larger_fonts: bool):
        # Apply style
        if theme == "Fusion":
            self.app.setStyle("Fusion")
        else:
            self.app.setStyle(self.system_theme)

        # Support larger fonts
        size = self.default_font_size
        if larger_fonts:
            size *= self.large_font_factor
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
        self.__DEFAULT_USER = "arpirobot"
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
