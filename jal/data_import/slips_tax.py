import uuid
import json
import logging
import requests
from urllib import parse
from datetime import datetime

from PySide6.QtCore import Signal, Slot, QUrl
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor, QWebEngineProfile, QWebEnginePage
from jal.db.settings import JalSettings
from jal.net.helpers import get_web_data, post_web_data
from jal.ui.ui_login_fns_dlg import Ui_LoginFNSDialog


#-----------------------------------------------------------------------------------------------------------------------
class RequestInterceptor(QWebEngineUrlRequestInterceptor):
    response_intercepted = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.session = None

    # At successful login ESIA page will give Response '302 Found' with URL to irkkt-mobile.nalog.ru which
    # contains authorization results. We can't intercept response so we block next request and
    # get parameters from it. Then communicate it via 'response_intercepted' signal
    def interceptRequest(self, info):
        url = info.firstPartyUrl().url()    # Get intercepted URL
        if str.startswith(url, "https://irkkt-mobile.nalog.ru:8888/"):
            info.block(True)
            params = dict(parse.parse_qsl(parse.urlsplit(url).query))
            auth_code = params['code']
            auth_state = params['state']
            logging.info(self.tr("ESIA login completed"))
            self.response_intercepted.emit(auth_code, auth_state)


#-----------------------------------------------------------------------------------------------------------------------
class LoginFNS(QDialog, Ui_LoginFNSDialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent=parent)
        self.setupUi(self)

        self.phone_number = ''
        self.web_session = requests.Session()
        self.web_session.headers['ClientVersion'] = '2.9.0'
        self.web_session.headers['Device-Id'] = str(uuid.uuid1())
        self.web_session.headers['Device-OS'] = 'Android'
        self.web_session.headers['Content-Type'] = 'application/json; charset=UTF-8'
        self.web_session.headers['Accept-Encoding'] = 'gzip'
        self.web_session.headers['User-Agent'] = 'okhttp/4.2.2'
        self.web_profile = QWebEngineProfile()
        self.web_interceptor = RequestInterceptor()
        self.web_interceptor.response_intercepted.connect(self.response_esia)
        self.web_profile.setRequestInterceptor(self.web_interceptor)
        self.ESIAWebView.setPage(QWebEnginePage(self.web_profile, self))

        self.LoginMethodTabs.currentChanged.connect(self.on_tab_changed)
        self.GetCodeBtn.clicked.connect(self.send_sms)
        self.SMSLoginBtn.clicked.connect(self.login_sms)
        self.FNSLoginBtn.clicked.connect(self.login_fns)

    def on_tab_changed(self, index):
        if index == 2: # ESIA login selected
            self.login_esia()

    def send_sms(self):
        client_secret = JalSettings().getValue('RuTaxClientSecret')
        self.phone_number = self.PhoneNumberEdit.text().replace('-', '')

        payload = '{' + f'"client_secret":"{client_secret}","phone":"{self.phone_number}"' + '}'
        response = self.web_session.post('https://irkkt-mobile.nalog.ru:8888/v2/auth/phone/request', data=payload)
        if response.status_code != 204:
            logging.error(self.tr("FNS login failed: ") + f"{response}/{response.text}")
        else:
            logging.info(self.tr("SMS was requested successfully"))
    
    def login_sms(self):
        if not self.phone_number:
            return
        client_secret = JalSettings().getValue('RuTaxClientSecret')
        code = self.CodeEdit.text()

        payload = '{' + f'"client_secret":"{client_secret}","code":"{code}","phone":"{self.phone_number}"' + '}'
        response = self.web_session.post('https://irkkt-mobile.nalog.ru:8888/v2/auth/phone/verify', data=payload)
        if response.status_code != 200:
            logging.error(self.tr("FNS login failed: ") + f"{response}/{response.text}")
            return
        logging.info(self.tr("FNS login successful: ") + f"{response.text}")
        json_content = json.loads(response.text)
        new_session_id = json_content['sessionId']
        new_refresh_token = json_content['refresh_token']
        settings = JalSettings()
        settings.setValue('RuTaxSessionId', new_session_id)
        settings.setValue('RuTaxRefreshToken', new_refresh_token)
        self.accept()

    def login_fns(self):
        client_secret = JalSettings().getValue('RuTaxClientSecret')
        inn = self.InnEdit.text()
        password = self.PasswordEdit.text()

        payload = '{' + f'"client_secret":"{client_secret}","inn":"{inn}","password":"{password}"' + '}'
        response = self.web_session.post('https://irkkt-mobile.nalog.ru:8888/v2/mobile/users/lkfl/auth', data=payload)
        if response.status_code != 200:
            logging.error(self.tr("FNS login failed: ") + f"{response}/{response.text}")
            return
        logging.info(self.tr("FNS login successful: ") + f"{response.text}")
        json_content = json.loads(response.text)
        new_session_id = json_content['sessionId']
        new_refresh_token = json_content['refresh_token']
        settings = JalSettings()
        settings.setValue('RuTaxSessionId', new_session_id)
        settings.setValue('RuTaxRefreshToken', new_refresh_token)
        self.accept()

    def login_esia(self):
        response = self.web_session.get('https://irkkt-mobile.nalog.ru:8888/v2/mobile/users/esia/auth/url')
        if response.status_code != 200:
            logging.error(self.tr("Get ESIA URL failed: ") + f"{response}/{response.text}")
            return
        json_content = json.loads(response.text)
        auth_url = json_content['url']
        self.ESIAWebView.load(QUrl(auth_url))

    @Slot()
    def response_esia(self, auth_code, state):
        client_secret = JalSettings().getValue('RuTaxClientSecret')
        payload = '{' + f'"authorization_code": "{auth_code}", "client_secret": "{client_secret}", "state": "{state}"' \
                  + '}'
        response = self.web_session.post('https://irkkt-mobile.nalog.ru:8888/v2/mobile/users/esia/auth', data=payload)
        if response.status_code != 200:
            logging.error(self.tr("ESIA login failed: ") + f"{response}/{response.text}")
            return
        logging.info(self.tr("ESIA login successful: ") + f"{response.text}")
        json_content = json.loads(response.text)
        new_session_id = json_content['sessionId']
        new_refresh_token = json_content['refresh_token']
        settings = JalSettings()
        settings.setValue('RuTaxSessionId', new_session_id)
        settings.setValue('RuTaxRefreshToken', new_refresh_token)
        self.accept()

#-----------------------------------------------------------------------------------------------------------------------
class SlipsTaxAPI:
    # Status codes that may be returned as result of class methods
    Failure = -1
    Success = 0
    Pending = 1

    def __init__(self):
        self.slip_json = None
        self.web_session = requests.Session()
        self.web_session.headers['ClientVersion'] = '2.9.0'
        self.web_session.headers['Device-Id'] = str(uuid.uuid1())
        self.web_session.headers['Device-OS'] = 'Android'
        self.web_session.headers['Content-Type'] = 'application/json; charset=UTF-8'
        self.web_session.headers['Accept-Encoding'] = 'gzip'
        self.web_session.headers['User-Agent'] = 'okhttp/4.2.2'

    def tr(self, text):
        return QApplication.translate("SlipsTaxAPI", text)

    def get_ru_tax_session(self):
        stored_id = JalSettings().getValue('RuTaxSessionId')
        if stored_id != '':
            return stored_id

        login_dialog = LoginFNS()
        if login_dialog.exec() == QDialog.Accepted:
            stored_id = JalSettings().getValue('RuTaxSessionId')
            if stored_id is not None:
                return stored_id

        logging.warning(self.tr("No Russian Tax SessionId available"))
        return ''

    def refresh_session(self):
        session_id = self.get_ru_tax_session()
        if not session_id:
            logging.info(self.tr("No valid session present"))
            return SlipsTaxAPI.Failure
        logging.info(self.tr("Refreshing session..."))
        client_secret = JalSettings().getValue('RuTaxClientSecret')
        refresh_token = JalSettings().getValue('RuTaxRefreshToken')
        self.web_session.headers['sessionId'] = session_id
        payload = '{' + f'"client_secret":"{client_secret}","refresh_token":"{refresh_token}"' + '}'
        response = self.web_session.post('https://irkkt-mobile.nalog.ru:8888/v2/mobile/users/refresh', data=payload)
        if response.status_code == 200:
            logging.info(self.tr("Session refreshed: ") + f"{response.text}")
            json_content = json.loads(response.text)
            new_session_id = json_content['sessionId']
            new_refresh_token = json_content['refresh_token']
            settings = JalSettings()
            settings.setValue('RuTaxSessionId', new_session_id)
            settings.setValue('RuTaxRefreshToken', new_refresh_token)
            return SlipsTaxAPI.Pending   # not Success as it is sent transparently to upper callers
        else:
            logging.error(self.tr("Can't refresh session, response: ") + f"{response}/{response.text}")
            JalSettings().setValue('RuTaxSessionId', '')
            if self.get_ru_tax_session():
                return SlipsTaxAPI.Failure
            else:
                return SlipsTaxAPI.Pending  # not Success as it is sent transparently to upper callers

    def get_slip(self, timestamp, amount, fn, fd, fp, slip_type):
        date_time = datetime.utcfromtimestamp(timestamp).strftime('%Y%m%dT%H%M%S')

        session_id = self.get_ru_tax_session()
        if session_id == '':
            return SlipsTaxAPI.Failure
        self.web_session.headers['sessionId'] = session_id
        payload = '{' + f'"qr": "t={date_time}&s={amount:.2f}&fn={fn}&i={fd}&fp={fp}&n={slip_type}"' + '}'
        response = self.web_session.post('https://irkkt-mobile.nalog.ru:8888/v2/ticket', data=payload)
        if response.status_code != 200:
            if response.status_code == 401:
                logging.info(self.tr("Unauthorized with reason: ") + f"{response.text}")
                return self.refresh_session()
            else:
                logging.error(
                    self.tr("Get ticket id failed: ") +
                    f"{response}/{response.text} for {payload}")
                return SlipsTaxAPI.Failure
        logging.info(self.tr("Slip found: " + response.text))
        json_content = json.loads(response.text)
        if json_content['status'] != 2:  # Valid slip status is 2, other statuses are not fully clear
            logging.warning(self.tr("Operation might be pending on server side. Trying again."))
            return SlipsTaxAPI.Pending
        url = "https://irkkt-mobile.nalog.ru:8888/v2/tickets/" + json_content['id']
        response = self.web_session.get(url)
        if response.status_code != 200:
            logging.error(self.tr("Get ticket failed: ") + f"{response}/{response.text}")
            return SlipsTaxAPI.Failure
        logging.info(self.tr("Slip loaded: " + response.text))
        self.slip_json = json.loads(response.text)
        return SlipsTaxAPI.Success

    #----------------------------------------------------------------------------------------------------------------
    # Gets company name by Russian INN
    # Returns short or long name if fount and initial INN otherwise
    def get_shop_name_by_inn(self, inn):
        if len(inn) != 10 and len(inn) != 12:
            logging.warning(self.tr("Incorrect length of INN. Can't get company name."))
            return inn
        region_list = "77,78,01,02,03,04,05,06,07,08,09,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,"\
                      "30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,"\
                      "61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,79,83,86,87,89,91,92,99"
        params = {'vyp3CaptchaToken': '', 'page': '', 'query': inn, 'region': region_list,
                  'PreventChromeAutocomplete': ''}
        token_data = json.loads(post_web_data('https://egrul.nalog.ru/', params))
        if 't' not in token_data:
            return inn
        result = json.loads(get_web_data('https://egrul.nalog.ru/search-result/' + token_data['t']))
        try:
            return result['rows'][0]['c']   # Return short name if exists
        except:
            pass
        try:
            return result['rows'][0]['n']   # Return long name if exists
        except:
            logging.warning(self.tr("Can't get company name from: ") + result)
            return inn
