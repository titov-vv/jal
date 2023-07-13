import re
import json
import logging
import requests
import requests_oauthlib
from urllib import parse
from oauthlib.oauth2 import MobileApplicationClient
from PySide6.QtCore import Qt, Slot, Signal, QMetaObject, QDateTime, QTimeZone, QUrl
from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineUrlScheme, \
    QWebEngineUrlSchemeHandler, QWebEngineUrlRequestJob
from jal.data_import.receipt_api.receipt_api import ReceiptAPI
from jal.db.settings import JalSettings
from jal.ui.ui_login_lidl_plus_dlg import Ui_LoginLidlPlusDialog


#-----------------------------------------------------------------------------------------------------------------------
class ReceiptEuLidlPlus(ReceiptAPI):
    receipt_pattern = r"A:.*\*B:.*\*C:PT\*D:FS\*E:N\*F:(?P<date>\d{8})\*G:FS (?P<shop_id>\d{4})\d(?P<register_id>\d{2})..\/.*\*H:.{1,70}\*I1:PT\*.*"
    # aux data is in form 888MMMMSSSSSSCCDDMMYYXFFFFFF
    # SSSSSS - receipt sequence number
    # YY, MM, DD - year, month, day of the receipt
    # CC cash register ID in the shop ID MMMM
    # X - unknown 1 digit
    # FFFFFF - FS part of fiscal data
    def __init__(self, qr_text='', aux_data='', params=None):
        super().__init__()
        self.access_token = ''
        self.slip_json = {}
        if params is None:
            parts = re.match(self.receipt_pattern, qr_text)
            if parts is None:
                raise ValueError(self.tr("Lidl QR available but pattern isn't recognized: " + qr_text))
            parts = parts.groupdict()
            self.date_time = QDateTime.fromString(parts['date'], 'yyyyMMdd')
            self.shop_id = int(parts['shop_id'])
            self.register_id = int(parts['register_id'])
            if len(aux_data) == 28:  # Get receipt sequence number from aux data or from the user
                self.seq_id = aux_data[7:13]
            else:
                self.seq_id, result = QInputDialog.getText(None, self.tr("Input Lidl receipt additional data"),
                                                           self.tr("Sequence #:"))
                if not result:
                    raise ValueError(self.tr("Can't get Lidl receipt without sequence number"))
            self.seq_id = int(self.seq_id.lstrip('0'))   # Get rid of any leading zeros and convert to int
        else:
            self.date_time = params['Date']
            self.shop_id = params['Shop #']
            self.register_id = params['Register #']
            self.seq_id = params['Sequence #']
        self.web_session = requests.Session()
        self.web_session.headers['User-Agent'] = "okhttp/4.10.0"

    @staticmethod
    def parameters_list() -> dict:
        parameters = {
            "Date": QDateTime.currentDateTime(QTimeZone.UTC).date(),
            "Shop #": 0,
            "Register #": 0,
            "Sequence #": 0
        }
        return parameters

    def activate_session(self) -> bool:
        self.access_token = JalSettings().getValue('EuLidlAccessToken', default='')
        if not self.access_token:
            self.__do_login()
        if not self.access_token:
            logging.warning(self.tr("No Lidl Plus access token available"))
            return False
        self.web_session.headers["Authorization"] = f"Bearer {self.access_token}"
        response = self.web_session.get("https://tickets.lidlplus.com/api/v2/PT/tickets?pageNumber=1&onlyFavorite=false&itemId=")  # Just to check authorization status
        if response.status_code == 200:
            return True
        if response.status_code == 401:
            logging.info(self.tr("Unauthorized with reason: ") + f"{response.text}")
            return self.__refresh_token()
        else:
            logging.error(self.tr("Lidl Plus API failed with: ") + f"{response.status_code}/{response.text}")
            return False

    def __refresh_token(self) -> bool:
        logging.info(self.tr("Refreshing Lidl Plus token..."))
        client_secret = JalSettings().getValue('EuLidlClientSecret')
        refresh_token = JalSettings().getValue('EuLidlRefreshToken')
        self.web_session.headers["Authorization"] = f"Basic {client_secret}"
        self.web_session.headers['Accept'] = "application/json"
        payload = {"grant_type": "refresh_token", "refresh_token": refresh_token}
        response = self.web_session.post("https://accounts.lidl.com/connect/token", data=payload)
        if response.status_code == 200:
            logging.info(self.tr("Lidl Plus token was refreshed: ") + f"{response.text}")
            json_content = json.loads(response.text)
            assert json_content['token_type'] == "Bearer"
            self.access_token = json_content['access_token']
            new_refresh_token = json_content['refresh_token']
            settings = JalSettings()
            settings.setValue('EuLidlAccessToken', self.access_token)
            settings.setValue('EuLidlRefreshToken', new_refresh_token)
            self.web_session.headers["Authorization"] = f"Bearer {self.access_token}"
            return True
        else:
            logging.error(self.tr("Can't refresh Lidl Plus token, response: ") + f"{response.status_code}/{response.text}")
            JalSettings().setValue('EuLidlAccessToken', '')
            self.access_token = ''
            return False

    def __do_login(self):
        login_dialog = LoginLidlPlus()
        if login_dialog.exec() == QDialog.Accepted:
            self.access_token = JalSettings().getValue('EuLidlAccessToken')

    def query_slip(self):
        ticket_id = f"2500{self.shop_id:04d}{self.register_id:02d}{self.date_time.toString('yyyyMMdd')}{self.seq_id:05d}"
        self.web_session.headers["Accept-Language"] = "PT"
        response = self.web_session.get(f"https://tickets.lidlplus.com/api/v2/PT/tickets/{ticket_id}")
        if response.status_code == 200:
            logging.info(self.tr("Receipt was loaded: " + response.text))
            self.slip_json = json.loads(response.text)
            self.slip_load_ok.emit()
        else:
            logging.error(self.tr("Receipt load failed: ") + f"{response.status_code}/{response.text} for {ticket_id}")
            self.slip_json = {}
            self.slip_load_failed.emit()

    def shop_name(self) -> str:
        return "Lidl"

    def datetime(self) -> QDateTime:
        if 'date' in self.slip_json:
            receipt_datetime = QDateTime.fromString(self.slip_json['date'], 'yyyy-MM-ddTHH:mm:ss')
        else:
            receipt_datetime = QDateTime()
        receipt_datetime.setTimeSpec(Qt.UTC)
        return receipt_datetime

    def slip_lines(self) -> list:
        lines = self.slip_json['itemsLine']
        for line in lines:
            line['quantity'] = float(line['quantity'].replace(',', '.'))
            line['unit_price'] = float(line.pop('currentUnitPrice').replace(',', '.'))
            line['amount'] = -float(line.pop('originalAmount').replace(',', '.'))
            if line['quantity'] != 1:
                line['name'] = f"{line['name']} ({line['quantity']:g} x {line['unit_price']:.2f})"
        return lines


#-----------------------------------------------------------------------------------------------------------------------
class LoginLidlPlus(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        self.ui = Ui_LoginLidlPlusDialog()
        self.ui.setupUi(self)

        self.verifier = ''
        self.lidl_client_id = "LidlPlusNativeClient"
        # Create scheme, handler and assign it to web-profile that is used for browser widget
        self.app_lidl_uri_scheme = QWebEngineUrlScheme(appDataHanlder.scheme)
        self.app_lidl_uri_scheme.setSyntax(QWebEngineUrlScheme.Syntax.Path)
        self.app_lidl_uri_scheme.setFlags(
            QWebEngineUrlScheme.Flag.ContentSecurityPolicyIgnored | QWebEngineUrlScheme.Flag.LocalAccessAllowed)
        QWebEngineUrlScheme.registerScheme(self.app_lidl_uri_scheme)
        self.app_lidl_uri_handler = appDataHanlder(self)
        self.app_lidl_uri_handler.data_received.connect(self.processResponse)
        self.web_profile = QWebEngineProfile(self)
        self.web_profile.installUrlSchemeHandler(appDataHanlder.scheme, self.app_lidl_uri_handler)
        self.ui.LidlPlusWebView.setPage(QWebEnginePage(self.web_profile, self))

    @Slot()
    def showEvent(self, event):
        super().showEvent(event)
        if self.running:
            return
        self.running = True
        # Call slot via queued connection, so it's called from the UI thread after the window has been shown
        QMetaObject().invokeMethod(self, "loadLoginPage", Qt.ConnectionType.QueuedConnection)

    @Slot()
    def loadLoginPage(self):
        # Get Login URL and open it in browser
        client = MobileApplicationClient(client_id=self.lidl_client_id)
        self.verifier = client.create_code_verifier(86)
        challenge = client.create_code_challenge(self.verifier, code_challenge_method='S256')
        oauth = requests_oauthlib.OAuth2Session(client_id=self.lidl_client_id,
                                                scope='openid profile offline_access lpprofile lpapis')
        oauth_url, oauth_state = oauth.authorization_url(url='https://accounts.lidl.com/')
        url = f"https://accounts.lidl.com/Account/Login?ReturnUrl=%2Fconnect%2Fauthorize%2Fcallback%3Fredirect_uri%3Dcom.lidlplus.app%253A%252F%252Fcallback"
        url += f"%26client_id%3D{self.lidl_client_id}"
        url += f"%26response_type%3Dcode%26state%3D{oauth_state}"  # "%26nonce%3Dt5Z_q8gekXoFRNmOVq2Ufg" - this part was omitted
        url += f"%26scope%3Dopenid%2520profile%2520offline_access%2520lpprofile%2520lpapis"
        url += f"%26code_challenge%3D{challenge}%26code_challenge_method%3DS256%26language%3DPT-PT%26track%3Dfalse%26force%3Dfalse%26Country%3DPT"
        self.ui.LidlPlusWebView.load(QUrl(url))   # Country and language are hard-coded to Portugal

    @Slot()
    def processResponse(self, params: dict):
        if 'code' not in params:
            QMessageBox().warning(None, self.tr("Login error"), self.tr("No auth code in callback URI"), QMessageBox.Ok)
            return
        client_secret = JalSettings().getValue('EuLidlClientSecret')
        # Get Auth token and display it
        s = requests.Session()
        s.headers["Authorization"] = f"Basic {client_secret}"
        s.headers['Accept'] = "application/json"
        data = {
            "grant_type": "authorization_code",
            "code": params['code'],
            "redirect_uri": "com.lidlplus.app://callback",
            "code_verifier": self.verifier
        }
        response = s.post("https://accounts.lidl.com/connect/token", data=data)
        if response.status_code != 200:
            logging.error(self.tr("Lidl Plus login failed: ") + f"{response.status_code}/{response.text}")
            return
        logging.info(self.tr("Lidl Plus login successful: ") + f"{response.text}")
        json_content = json.loads(response.text)
        assert json_content['token_type'] == "Bearer"
        new_access_token = json_content['access_token']
        new_refresh_token = json_content['refresh_token']
        settings = JalSettings()
        settings.setValue('EuLidlAccessToken', new_access_token)
        settings.setValue('EuLidlRefreshToken', new_refresh_token)
        self.accept()


# ----------------------------------------------------------------------------------------------------------------------
# Final URI is returned in form of "com.lidlplus.app://callback?code=..&scope=..&state=..&session_state=..", so
# it requires a special handler for "protocol" "com.lidlplus.app"
# Signal "data_received" is emitted when URI is processed, its parameter contains dictionary with URI parameters
# Page is redirected to "about:blank" in order to clean the browser window
class appDataHanlder(QWebEngineUrlSchemeHandler):
    scheme = b"com.lidlplus.app"
    data_received = Signal(dict)

    def __init__(self, parent = None):
        super().__init__(parent)

    def requestStarted(self, job: QWebEngineUrlRequestJob) -> None:
        url = job.requestUrl().url()
        params = dict(parse.parse_qsl(parse.urlsplit(url).query))
        job.fail(QWebEngineUrlRequestJob.Error.NoError)   # Stop processing but without an error
        self.data_received.emit(params)  # Dict contains 'code', 'scope', 'state' and 'session_state' elements
