from typing import Dict, List

from qtpy.QtCore import QSize, QFile, QIODevice, QDirIterator, QFileInfo, QDir, QSettings
from qtpy.QtGui import QTextDocument, QAbstractTextDocumentLayout
from qtpy.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QApplication, QStyle, QStyleFactory


WIFI_COUNTRY_CODES = ["AF", "AL", "DZ", "AS", "AD", "AO", "AI", "AQ", "AG", "AR", "AM", "AW", "AU", "AT", "AZ", "BS", "BH", "BD", "BB", "BY", "BE", "BZ", "BJ", "BM", "BT", "BO", "BQ", "BA", "BW", "BV", "BR", "IO", "BN", "BG", "BF", "BI", "KH", "CM", "CA", "CV", "KY", "CF", "TD", "CL", "CN", "CX", "CC", "CO", "KM", "CG", "CD", "CK", "CR", "CI", "HR", "CU", "CW", "CY", "CZ", "DK", "DJ", "DM", "DO", "EC", "EG", "SV", "GQ", "ER", "EE", "SZ", "ET", "FK", "FO", "FJ", "FI", "FR", "GF", "PF", "TF", "GA", "GM", "GE", "DE", "GH", "GI", "GR", "GL", "GD", "GP", "GU", "GT", "GG", "GN", "GW", "GY", "HT", "HM", "VA", "HN", "HK", "HU", "IS", "IN", "ID", "IR", "IQ", "IE", "IM", "IL", "IT", "JM", "JP", "JE", "JO", "KZ", "KE", "KI", "KP", "KR", "KW", "KG", "LA", "LV", "LB", "LS", "LR", "LY", "LI", "LT", "LU", "MO", "MG", "MW", "MY", "MV", "ML", "MT", "MH", "MQ", "MR", "MU", "YT", "MX", "FM", "MD", "MC", "MN", "ME", "MS", "MA", "MZ", "MM", "NA", "NR", "NP", "NL", "NC", "NZ", "NI", "NE", "NG", "NU", "NF", "MK", "MP", "NO", "OM", "PK", "PW", "PS", "PA", "PG", "PY", "PE", "PH", "PN", "PL", "PT", "PR", "QA", "RE", "RO", "RU", "RW", "BL", "SH", "KN", "LC", "MF", "PM", "VC", "WS", "SM", "ST", "SA", "SN", "RS", "SC", "SL", "SG", "SX", "SK", "SI", "SB", "SO", "ZA", "GS", "SS", "ES", "LK", "SD", "SR", "SJ", "SE", "CH", "SY", "TW", "TJ", "TZ", "TH", "TL", "TG", "TK", "TO", "TT", "TN", "TR", "TM", "TC", "TV", "UG", "UA", "AE", "GB", "UM", "US", "UY", "UZ", "VU", "VE", "VN", "VG", "VI", "WF", "EH", "YE", "ZM", "ZW", "AX"]


class ThemeManager:
    """
    Handles managing custom stylesheet supporting multiple "color themes".
    Custom stylesheet uses placeholder variables (@var_name@). There are several
    CSV files containing mappings for these placeholder variables.
    Each is considered its own "color theme".
    This class manages loading the template stylesheet and substituting values from CSV files.
    """
    def __init__(self):
        self.__BASE_STYLESHEET = ":/stylesheet.qss"
        self.__THEME_PATH = ":/stylesheet-vars/"
        self.__themes: List[str] = []
        self.__app: QApplication = None
        self.__current_theme = ""
        self.__current_csv_vars: Dict[str, str] = {}

    def set_app(self, app: QApplication):
        self.__app = app
        # Custom stylesheet used is designed for fusion base
        self.__app.setStyle(QStyleFactory.create("Fusion"))

    def load_themes(self):
        # Load a list of theme names, but do not generate stylesheets yet.
        # Pre-generating multiple stylesheets wastes memory
        self.__themes.clear()
        iterator = QDirIterator(self.__THEME_PATH)
        while iterator.hasNext():
            info = QFileInfo(iterator.next())
            if info.completeSuffix().lower() == "csv":
                self.__themes.append(info.baseName())

    def themes(self) -> List[str]:
        return self.__themes.copy()

    def current_theme(self) -> str:
        return self.__current_theme

    def apply_theme(self, theme: str, larger_fonts: bool) -> bool:
        if theme is None:
            self.__current_theme = ""
            self.__app.setStyleSheet("")
            return True

        if theme not in self.__themes:
            return False

        self.__current_theme = theme

        if larger_fonts:
            font_size = 11
        else:
            font_size = 9

        # Load stylesheet. This is a stylesheet with placeholders. It cannot be used directly
        stylesheet_str = ""
        stylesheet_file = QFile(":/stylesheet.qss")
        if stylesheet_file.open(QIODevice.ReadOnly):
            stylesheet_str = bytes(stylesheet_file.readAll()).decode()
        else:
            return False
        stylesheet_file.close()

        stylesheet_str = stylesheet_str.replace("|default_font_size|", str(font_size))

        # Clear before loading vars from CSV
        self.__current_csv_vars.clear()

        # Substitute values for placeholders in stylesheet
        vars_file = QFile(f"{self.__THEME_PATH}/{theme}.csv")
        if vars_file.open(QIODevice.ReadOnly):
            for line in bytes(vars_file.readAll()).decode().splitlines(False):
                # Index 0 = variable, Index 1 = value
                parts = line.replace(", ", ",").split(",")
                stylesheet_str = stylesheet_str.replace(f"@{parts[0]}@", parts[1])

                # If duplicate vars in CSV take the first as that will replace the placeholder in the stylesheet
                if parts[0] not in self.__current_csv_vars:
                    self.__current_csv_vars[parts[0]] = parts[1]
        else:
            return False

        self.__app.setStyleSheet(stylesheet_str)

        return True

    def get_variable(self, var: str) -> str:
        """
        Get the value of a given variable for the current theme.
        This information is saved when the theme is applied
        and thus does not require reparsing the CSV file each time
        """
        if var in self.__current_csv_vars:
            return self.__current_csv_vars[var]
        return ""

    def get_variable_for_theme(self, var: str, theme: str = None) -> str:
        """
        Parse the variables CSV file for the theme withthe given name.
        Return the value of the requested variable.
        """
        if theme is None:
            theme = self.__current_theme
        if theme not in self.__themes:
            return None
        vars_file = QFile(f"{self.__THEME_PATH}/{theme}.csv")
        if vars_file.open(QIODevice.ReadOnly):
            for line in bytes(vars_file.readAll()).decode().splitlines(False):
                # Index 0 = variable, Index 1 = value
                parts = line.replace(", ", ",").split(",")
                if parts[0] == var:
                    return parts[1]
        return ""

    def current_stylesheet(self) -> str:
        return self.__app.styleSheet()


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
        self.__DEFAULT_THEME = "Light"
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
