from PySide6.QtCore import Qt, QObject, Slot, SLOT
from PySide6.QtWidgets import QApplication
from jal.widgets.theme import is_dark_theme
try:
    from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusVariant
except ImportError:   # Qt builds its D-Bus module on unix-like systems only
    QDBusConnection = None


# ----------------------------------------------------------------------------------------------------------------------
# Keeps jal in step with the light/dark preference of a freedesktop desktop Linux environment.
#
# Qt learns that preference from its platform theme, and under GNOME the platform theme is the GTK3 one, which can
# only report what GTK3 itself is set to. GNOME's Settings->Appearance->Style switch doesn't touch GTK3 though: it
# writes the 'color-scheme' key of the XDG desktop portal, which is what GTK4 and other modern applications read.
# A GNOME user in dark mode therefore leaves Qt convinced that the desktop is light, unless GTK3's own dark flag
# happens to be set by hand in ~/.config/gtk-3.0/settings.ini.
#
# So the preference is read from the portal here and handed to Qt via QStyleHints.setColorScheme(). Qt rebuilds the
# palette from it, which is all that is needed - every color jal paints is derived from the palette (see
# jal.widgets.theme), and QStyleHints keeps reporting the scheme for the two charts that ask for it directly.
#
# Anyone who has themed Qt on purpose (qt6ct, a Plasma color scheme, -style on the command line) is left alone:
# the preference is applied only when the palette actually in use contradicts it.
class DesktopColorScheme(QObject):
    SERVICE = "org.freedesktop.portal.Desktop"
    PATH = "/org/freedesktop/portal/desktop"
    INTERFACE = "org.freedesktop.portal.Settings"
    NAMESPACE = "org.freedesktop.appearance"
    KEY = "color-scheme"
    # Values of the portal's 'color-scheme' key. The third one, 0, is "no preference": the desktop states nothing
    # and whatever Qt has decided on its own stands. GNOME reports it for its light style, which is a statement of
    # sorts, but not one to read as "force this application light" - other desktops mean it literally.
    PORTAL_SCHEMES = {1: Qt.ColorScheme.Dark, 2: Qt.ColorScheme.Light}

    def __init__(self, application: QApplication):
        super().__init__(application)
        self._portal = QDBusInterface(self.SERVICE, self.PATH, self.INTERFACE, QDBusConnection.sessionBus(), self)
        self._imposed = False   # True while the scheme in effect is the one this class has set

    # Applies the current preference and starts watching for changes of it. False if this desktop has no portal to ask.
    def start(self) -> bool:
        if not self._portal.isValid():
            return False
        QDBusConnection.sessionBus().connect(self.SERVICE, self.PATH, self.INTERFACE, "SettingChanged",
                                             self, SLOT("onSettingChanged(QString,QString,QDBusVariant)"))
        self.apply()
        return True

    @Slot(str, str, QDBusVariant)
    def onSettingChanged(self, namespace: str, key: str, _value) -> None:
        if namespace == self.NAMESPACE and key == self.KEY:
            self.apply()   # the value comes with the signal, but re-reading keeps one code path for it

    def preference(self) -> Qt.ColorScheme:
        answer = self._portal.call("Read", self.NAMESPACE, self.KEY)
        if answer.errorName() or not answer.arguments():   # the key is optional, a portal may not implement it
            return Qt.ColorScheme.Unknown
        value = answer.arguments()[0]
        while isinstance(value, QDBusVariant):   # the portal wraps the value into a variant, inside another variant
            value = value.variant()
        return self.PORTAL_SCHEMES.get(value, Qt.ColorScheme.Unknown)

    def apply(self) -> None:
        scheme = self.preference()
        if scheme == Qt.ColorScheme.Unknown:
            if self._imposed:   # the desktop has dropped its preference - Qt's own choice takes the decision back
                QApplication.styleHints().setColorScheme(Qt.ColorScheme.Unknown)
                self._imposed = False
        elif (scheme == Qt.ColorScheme.Dark) != is_dark_theme():   # the palette in use contradicts the desktop
            QApplication.styleHints().setColorScheme(scheme)
            self._imposed = True


# ----------------------------------------------------------------------------------------------------------------------
def follow_desktop_color_scheme(application: QApplication) -> None:
    if QDBusConnection is None or not QDBusConnection.sessionBus().isConnected():
        return   # not a freedesktop session (Windows, macOS): Qt's own idea of the colour scheme is the best there is
    DesktopColorScheme(application).start()   # parented to the application, which keeps it alive to get the signals
