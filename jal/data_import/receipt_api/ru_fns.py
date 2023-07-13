import uuid
import logging
import json
import requests
import time
from urllib import parse
from decimal import Decimal
from PySide6.QtCore import Qt, Signal, Slot, QUrl, QDateTime, QTimeZone
from PySide6.QtWidgets import QDialog
from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor, QWebEngineProfile, QWebEnginePage
from jal.data_import.receipt_api.receipt_api import ReceiptAPI
from jal.db.settings import JalSettings
from jal.net.helpers import get_web_data, post_web_data
from jal.ui.ui_login_fns_dlg import Ui_LoginFNSDialog


#-----------------------------------------------------------------------------------------------------------------------
class ReceiptRuFNS(ReceiptAPI):
    MAX_ATTEMPTS = 5
    timestamp_patterns = ['yyyyMMddTHHmm', 'yyyyMMddTHHmmss', 'yyyy-MM-ddTHH:mm', 'yyyy-MM-ddTHH:mm:ss']

    def __init__(self, qr_text='', aux_data='', params=None):
        super().__init__()
        self.session_id = ''
        self.slip_json = {}
        if params is None:
            try:
                params = parse.parse_qs(qr_text)
                self.date_time = ''
                for timestamp_pattern in self.timestamp_patterns:
                    datetime_value = QDateTime.fromString(params['t'][0], timestamp_pattern)
                    if datetime_value.isValid():
                        self.date_time = datetime_value.toString("yyyyMMddThhmmss")
                        break
                if not self.date_time:
                    raise ValueError(self.tr("FNS QR available but date/time pattern isn't recognized: " + qr_text))
                self.amount = float(params['s'][0])
                self.fn = params['fn'][0]
                self.fd = params['i'][0]
                self.fp = params['fp'][0]
                self.op_type = params['n'][0]
            except Exception:
                raise ValueError(self.tr("FNS QR available but pattern isn't recognized: " + qr_text))
        else:
            self.date_time = params['Дата/время'].toString("yyyyMMddThhmmss")
            self.fn = params['ФН']
            self.fd = params['ФД']
            self.fp = params['ФП']
            self.amount = float(params['Сумма'])
            self.op_type = params['Тип']
        self.web_session = requests.Session()
        self.web_session.headers['ClientVersion'] = '2.9.0'
        self.web_session.headers['Device-Id'] = str(uuid.uuid1())
        self.web_session.headers['Device-OS'] = 'Android'
        self.web_session.headers['Content-Type'] = 'application/json; charset=UTF-8'
        self.web_session.headers['Accept-Encoding'] = 'gzip'
        self.web_session.headers['User-Agent'] = 'okhttp/4.2.2'

    @staticmethod
    def parameters_list() -> dict:
        parameters = {
            "Дата/время": QDateTime.currentDateTime(QTimeZone.UTC),
            "ФН": '',
            "ФД": '',
            "ФП": '',
            "Сумма": Decimal('0'),
            "Тип": {1: "Покупка", 2: "Возврат"}
        }
        return parameters

    def activate_session(self) -> bool:
        self.session_id = JalSettings().getValue('RuTaxSessionId', default='')
        if not self.session_id:
            self.__do_login()
        if not self.session_id:
            logging.warning(self.tr("No FNS SessionId available"))
            return False
        self.web_session.headers['sessionId'] = self.session_id
        response = self.web_session.get('https://irkkt-mobile.nalog.ru:8888/v2/tickets')  # Just to check authorization status
        if response.status_code == 200:
            return True
        if response.status_code == 401:
            logging.info(self.tr("Unauthorized with reason: ") + f"{response.text}")
            return self.__refresh_session()
        else:
            logging.error(self.tr("FNS API failed with: ") + f"{response.status_code}/{response.text}")
            return False

    def __refresh_session(self) -> bool:
        if not self.session_id:
            return False
        logging.info(self.tr("Refreshing FNS session..."))
        client_secret = JalSettings().getValue('RuTaxClientSecret')
        refresh_token = JalSettings().getValue('RuTaxRefreshToken')
        self.web_session.headers['sessionId'] = self.session_id
        payload = '{' + f'"client_secret":"{client_secret}","refresh_token":"{refresh_token}"' + '}'
        response = self.web_session.post('https://irkkt-mobile.nalog.ru:8888/v2/mobile/users/refresh', data=payload)
        if response.status_code == 200:
            logging.info(self.tr("FNS session refreshed: ") + f"{response.text}")
            json_content = json.loads(response.text)
            self.session_id = json_content['sessionId']
            new_refresh_token = json_content['refresh_token']
            settings = JalSettings()
            settings.setValue('RuTaxSessionId', self.session_id)
            settings.setValue('RuTaxRefreshToken', new_refresh_token)
            self.web_session.headers['sessionId'] = self.session_id
            return True
        else:
            logging.error(self.tr("Can't refresh FNS session, response: ") + f"{response.status_code}/{response.text}")
            JalSettings().setValue('RuTaxSessionId', '')
            self.session_id = ''
            return False

    def __do_login(self):
        login_dialog = LoginFNS()
        if login_dialog.exec() == QDialog.Accepted:
            self.session_id = JalSettings().getValue('RuTaxSessionId')

    def query_slip(self):
        json_content = {}
        payload = '{' + f'"qr": "t={self.date_time}&s={self.amount:.2f}&fn={self.fn}&i={self.fd}&fp={self.fp}&n={self.op_type}"' + '}'
        for i in range(self.MAX_ATTEMPTS):
            response = self.web_session.post('https://irkkt-mobile.nalog.ru:8888/v2/ticket', data=payload)
            if response.status_code != 200:
                logging.error(self.tr("Get ticket id failed: ") + f"{response.status_code}/{response.text} for {payload}")
                return
            logging.info(self.tr("Receipt found: " + response.text))
            json_content = json.loads(response.text)
            if json_content['status'] == 2:  # Valid slip status is 2, other statuses are not fully clear
                break
            logging.warning(self.tr("Operation might be pending on server side. Trying again."))
            time.sleep(0.5)  # wait half a second before next attempt
        if json_content['status'] == 2:
            url = "https://irkkt-mobile.nalog.ru:8888/v2/tickets/" + json_content['id']
            response = self.web_session.get(url)
            if response.status_code != 200:
                logging.error(self.tr("Receipt load failed: ") + f"{response}/{response.text}")
                self.slip_load_failed.emit()
            logging.info(self.tr("Receipt was loaded: " + response.text))
            self.slip_json = self.__slip_data(json.loads(response.text))
            self.slip_load_ok.emit()
        else:
            self.slip_load_failed.emit()

    # Slip data might be in a root element or in ticket/document/receipt
    # This method returns actual slip as result
    def __slip_data(self, json_data) -> dict:
        if 'ticket' in json_data:
            sub = json_data['ticket']
            if 'document' in sub:
                sub = sub['document']
                if 'receipt' in sub:
                    receipt = sub['receipt']
                else:
                    logging.error(self.tr("Can't find 'receipt' tag in json 'document' from FNS"))
                    return {}
            else:
                logging.error(self.tr("Can't find 'document' tag in json 'ticket' from FNS"))
                return {}
        else:
            receipt = json_data
        return receipt

    # ----------------------------------------------------------------------------------------------------------------
    # Gets company name by Russian INN
    # Returns short or long name if fount and initial INN otherwise
    def shop_name(self) -> str:
        if 'user' in self.slip_json:
            return self.slip_json['user']
        if 'userInn' in self.slip_json:
            inn = self.slip_json['userInn']
        else:
            return ''
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

    def datetime(self) -> QDateTime:
        if 'dateTime' in self.slip_json:
            receipt_datetime = QDateTime.fromSecsSinceEpoch(int(self.slip_json['dateTime']))
        else:
            receipt_datetime = QDateTime()
        receipt_datetime.setTimeSpec(Qt.UTC)
        return receipt_datetime

    def slip_lines(self) -> list:
        PURCHASE = 1
        RETURN = 2

        if 'operationType' in self.slip_json:
            operation = int(self.slip_json['operationType'])
        else:
            logging.error(self.tr("Can't find 'operationType' tag in json 'ticket'"))
            return []
        lines = self.slip_json['items']
        for line in lines:
            line['unit_price'] = line.pop('price') / 100
            sign = -1 if operation == PURCHASE else +1
            line['amount'] = sign * line.pop('sum') / 100
            if line['quantity'] != 1:
                line['name'] = f"{line['name']} ({line['quantity']:g} x {line['unit_price']:.2f})"
        return lines


#-----------------------------------------------------------------------------------------------------------------------
class LoginFNS(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_LoginFNSDialog()
        self.ui.setupUi(self)

        self.phone_number = ''
        self.web_session = requests.Session()
        self.web_session.headers['ClientVersion'] = '2.9.0'
        self.web_session.headers['Device-Id'] = str(uuid.uuid1())
        self.web_session.headers['Device-OS'] = 'Android'
        self.web_session.headers['Content-Type'] = 'application/json; charset=UTF-8'
        self.web_session.headers['Accept-Encoding'] = 'gzip'
        self.web_session.headers['User-Agent'] = 'okhttp/4.2.2'
        self.web_profile = QWebEngineProfile(self)
        self.web_interceptor = RequestInterceptor(self)
        self.web_interceptor.response_intercepted.connect(self.response_esia)
        self.web_profile.setUrlRequestInterceptor(self.web_interceptor)
        self.ui.ESIAWebView.setPage(QWebEnginePage(self.web_profile, self))

        self.ui.LoginMethodTabs.currentChanged.connect(self.on_tab_changed)
        self.ui.GetCodeBtn.clicked.connect(self.send_sms)
        self.ui.SMSLoginBtn.clicked.connect(self.login_sms)
        self.ui.FNSLoginBtn.clicked.connect(self.login_fns)

    def on_tab_changed(self, index):
        if index == 2:  # ESIA login selected
            self.login_esia()

    def send_sms(self):
        client_secret = JalSettings().getValue('RuTaxClientSecret')
        self.phone_number = self.ui.PhoneNumberEdit.text().replace('-', '')

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
        code = self.ui.CodeEdit.text()

        payload = '{' + f'"client_secret":"{client_secret}","code":"{code}","phone":"{self.phone_number}"' + '}'
        response = self.web_session.post('https://irkkt-mobile.nalog.ru:8888/v2/auth/phone/verify', data=payload)
        if response.status_code != 200:
            logging.error(self.tr("FNS login failed: ") + f"{response.status_code}/{response.text}")
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
        inn = self.ui.InnEdit.text()
        password = self.ui.PasswordEdit.text()

        payload = '{' + f'"client_secret":"{client_secret}","inn":"{inn}","password":"{password}"' + '}'
        response = self.web_session.post('https://irkkt-mobile.nalog.ru:8888/v2/mobile/users/lkfl/auth', data=payload)
        if response.status_code != 200:
            logging.error(self.tr("FNS login failed: ") + f"{response.status_code}/{response.text}")
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
            logging.error(self.tr("Get ESIA URL failed: ") + f"{response.status_code}/{response.text}")
            return
        json_content = json.loads(response.text)
        auth_url = json_content['url']
        self.ui.ESIAWebView.load(QUrl(auth_url))

    @Slot()
    def response_esia(self, auth_code, state):
        client_secret = JalSettings().getValue('RuTaxClientSecret')
        payload = '{' + f'"authorization_code": "{auth_code}", "client_secret": "{client_secret}", "state": "{state}"' \
                  + '}'
        response = self.web_session.post('https://irkkt-mobile.nalog.ru:8888/v2/mobile/users/esia/auth', data=payload)
        if response.status_code != 200:
            logging.error(self.tr("ESIA login failed: ") + f"{response.status_code}/{response.text}")
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
class RequestInterceptor(QWebEngineUrlRequestInterceptor):
    response_intercepted = Signal(str, str)

    def __init__(self, parent = None):
        super().__init__(parent)
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
