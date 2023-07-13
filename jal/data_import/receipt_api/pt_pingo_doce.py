import re
import json
import logging
import requests
from decimal import Decimal
from PySide6.QtCore import Qt, QDateTime, QTimeZone
from PySide6.QtWidgets import QDialog
from jal.data_import.receipt_api.receipt_api import ReceiptAPI
from jal.db.settings import JalSettings
from jal.ui.ui_login_pingo_doce_dlg import Ui_LoginPingoDoceDialog


#-----------------------------------------------------------------------------------------------------------------------
class ReceiptPtPingoDoce(ReceiptAPI):
    receipt_pattern = r"A:.*\*B:.*\*C:PT\*D:FS\*E:N\*F:(?P<date>\d{8})\*G:FS (?P<shop_id>\d{4})(?P<register_id>\d{3}).*\/.*\*H:.{1,70}\*I1:PT\*.*\*O:(?P<amount>\d{1,}\.\d\d)\*.*"
    # aux data is in form SSSSSSYYYYMMDDhhmmNNNNCCCCMMMM
    # SSSSSS - receipt sequence number
    # YYYY, MM, DD, hh, mm - year, month, day and hour/minute of the receipt
    # NNNN - unknown 4 digits
    # CCCC cash register ID in the shop ID MMMM
    def __init__(self, qr_text='', aux_data='', params=None):
        super().__init__()
        self.aux_data = aux_data
        self.access_token = ''
        self.user_profile = {}
        self.receipts = []
        self.slip_json = {}
        if params is None:
            parts = re.match(self.receipt_pattern, qr_text)
            if parts is None:
                raise ValueError(self.tr("Pingo Doce QR available but pattern isn't recognized: " + qr_text))
            parts = parts.groupdict()
            self.date_time = QDateTime.fromString(parts['date'], 'yyyyMMdd')
            self.shop_id = int(parts['shop_id'].lstrip('0'))
            self.total_amount = float(parts['amount'])
        else:
            self.date_time = params['Date/Time']
            self.shop_id = params['Shop #']
            self.total_amount = float(params['Total'])
        self.web_session = requests.Session()
        self.web_session.headers['User-Agent'] = "okhttp/4.10.0"
        self.web_session.headers['Content-Type'] = 'application/json; charset=UTF-8'

    @staticmethod
    def parameters_list() -> dict:
        parameters = {
            "Date/Time": QDateTime.currentDateTime(QTimeZone.UTC),
            "Shop #": 0,
            "Total": Decimal('0')
        }
        return parameters

    def activate_session(self) -> bool:
        self.access_token = JalSettings().getValue('PtPingoDoceAccessToken', default='')
        self.user_profile = json.loads(JalSettings().getValue('PtPingoDoceUserProfile', default='{}'))
        if not self.access_token:
            self.__do_login()
        if not self.access_token or not self.user_profile:
            logging.warning(self.tr("No Pingo Doce access token available"))
            return False
        self.web_session.headers["Authorization"] = f"Bearer {self.access_token}"
        self.web_session.headers["pdapp-storeId"] = "-1"
        self.web_session.headers["pdapp-cardNumber"] = f"PDOM|{self.user_profile['ompdCard']}|{self.user_profile['householdId']}"
        self.web_session.headers["pdapp-lcid"] = self.user_profile['loyaltyId']
        self.web_session.headers["pdapp-hid"] = self.user_profile['householdId']
        payload = '{"pmCard":"' + self.user_profile['ompdCard'] + '"}'
        response = self.web_session.post("https://app-proxy.pingodoce.pt/api/v2/user/cardassociations/savings", data=payload)
        if response.status_code == 401:
            logging.info(self.tr("Unauthorized with reason: ") + f"{response.text}")
            if self.__refresh_token():
                self.web_session.headers["Authorization"] = f"Bearer {self.access_token}"
                self.web_session.headers["pdapp-storeId"] = "-1"
                self.web_session.headers["pdapp-cardNumber"] = f"PDOM|{self.user_profile['ompdCard']}|{self.user_profile['householdId']}"
                self.web_session.headers["pdapp-lcid"] = self.user_profile['loyaltyId']
                self.web_session.headers["pdapp-hid"] = self.user_profile['householdId']
            else:
                return False
        elif response.status_code != 200:
            logging.error(self.tr("Pingo Doce API failed with: ") + f"{response.status_code}/{response.text}")
            return False
        response = self.web_session.get("https://app-proxy.pingodoce.pt/api/v2/user/transactionsHistory/chart?filter=FILTER_BY_30_DAYS")
        if response.status_code != 200:
            logging.error(self.tr("Pingo Doce API filter failed with: ") + f"{response.status_code}/{response.text}")
            return False
        page = 1
        while page>0:
            logging.info(f"Loading {page} page of Pingo Doce receipts")
            response = self.web_session.get(f"https://app-proxy.pingodoce.pt/api/v2/user/transactionsHistory?pageNumber={page}&pageSize=20")
            if response.status_code != 200:
                logging.error(self.tr("Pingo Doce API history failed: ") + f"{response.status_code}/{response.text}")
                return False
            receipts = json.loads(response.text)
            page = -1 if len(receipts) < 20 else page + 1  # Go to next page or stop loading
            for receipt in receipts:
                self.receipts.append({"id": receipt['transactionId'], "shop_id": receipt['storeId'],
                                      "date": receipt['transactionDate'], "amount": float(receipt['total'])})
        logging.info(f"Pingo Doce list of receipts loaded: {self.receipts}")
        return True

    def __refresh_token(self) -> bool:
        logging.info(self.tr("Refreshing Pingo Doce token..."))
        self.access_token = JalSettings().getValue('PtPingoDoceAccessToken', default='')
        refresh_token = JalSettings().getValue('PtPingoDoceRefreshToken', default='')
        self.web_session = requests.Session()   # Need to start a clean session here
        self.web_session.headers['User-Agent'] = "okhttp/4.10.0"
        self.web_session.headers["Authorization"] = f"Bearer {self.access_token}"
        payload = {"client_id": "pdappclient", "grant_type": "refresh_token", "refresh_token": refresh_token}
        response = self.web_session.post("https://app-proxy.pingodoce.pt/connect/token", data=payload)
        if response.status_code == 200:
            logging.info(self.tr("Pingo Doce token was refreshed: ") + f"{response.text}")
            json_content = json.loads(response.text)
            assert json_content['token_type'] == "Bearer"
            self.access_token = json_content['access_token']
            new_refresh_token = json_content['refresh_token']
            settings = JalSettings()
            settings.setValue('PtPingoDoceAccessToken', self.access_token)
            settings.setValue('PtPingoDoceRefreshToken', new_refresh_token)
        else:
            logging.error(self.tr("Can't refresh Pingo Doce token, response: ") + f"{response.status_code}/{response.text}")
            JalSettings().setValue('PtPingoDoceAccessToken', '')
            self.access_token = ''
            return False
        response = self.web_session.get("https://app-proxy.pingodoce.pt/api/v2/user/userprofiles")
        if response.status_code != 200:
            logging.error(self.tr("Can't get Pingo Doce profile, response: ") + f"{response.status_code}/{response.text}")
            return False
        logging.info(self.tr("Pingo Doce profile was loaded: ") + f"{response.text}")
        self.user_profile = json.loads(response.text)
        settings.setValue('PtPingoDoceUserProfile', json.dumps(self.user_profile))
        return True

    def __do_login(self):
        login_dialog = LoginPingoDoce()
        if login_dialog.exec() == QDialog.Accepted:
            self.access_token = JalSettings().getValue('PtPingoDoceAccessToken')

    def query_slip(self):
        tickets = [x for x in self.receipts if x['shop_id'] == self.shop_id and
                   x['amount'] == self.total_amount and x['date'] == self.date_time.toString('yyyy-MM-ddT00:00:00')]
        if len(tickets) == 1:
            response = self.web_session.get(f"https://app-proxy.pingodoce.pt/api/v2/user/transactionsHistory/details?id={tickets[0]['id']}")
            if response.status_code == 200:
                logging.info(self.tr("Receipt was loaded: " + response.text))
                self.slip_json = json.loads(response.text)
                self.slip_load_ok.emit()
            else:
                logging.error(self.tr("Receipt load failed: ") + f"{response.status_code}/{response.text} for {tickets[0]['id']}")
                self.slip_json = {}
                self.slip_load_failed.emit()
        else:
            if len(tickets) == 0:
                logging.warning(self.tr("Receipt was not found in available list"))
            else:
                logging.warning(self.tr("Several similar receipts was found: ") + {tickets})
            self.slip_json = {}
            self.slip_load_failed.emit()

    def shop_name(self) -> str:
        return "Pingo Doce"

    def datetime(self) -> QDateTime:
        receipt_datetime = self.date_time
        receipt_datetime.setTimeSpec(Qt.UTC)
        return receipt_datetime

    def slip_lines(self) -> list:
        lines = self.slip_json['products']
        for line in lines:
            line['quantity'] = float(line.pop('purchaseQuantity').replace(',', '.'))
            line['amount'] = -float(line.pop('purchasePrice').replace(',', '.'))
            line['unit_price'] = abs(line['amount'] / line['quantity'])
            if line['quantity'] != 1:
                line['name'] = f"{line['name']} ({line['quantity']:g} x {line['unit_price']:.2f})"
        return lines


#-----------------------------------------------------------------------------------------------------------------------
class LoginPingoDoce(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_LoginPingoDoceDialog()
        self.ui.setupUi(self)
        self.ui.LoginBtn.pressed.connect(self.do_login)
        self.phone_number = ''
        self.web_session = requests.Session()
        self.web_session.headers['User-Agent'] = 'okhttp/4.2.2'

    def do_login(self):
        self.phone_number = self.ui.PhoneNumberEdit.text().replace('-', '')[4:]  # Take phone number without country code
        self.web_session.headers['Content-Type'] = 'application/json; charset=UTF-8'
        payload = '{' + f'"phoneNumber":"{self.phone_number}"' + '}'
        response = self.web_session.post("https://app-proxy.pingodoce.pt/api/v2/identity/sms/verifyNumber", data=payload)
        if response.status_code != 200:
            logging.error(self.tr("Pingo Doce phone verification failed: ") + f"{response.status_code}/{response.text}")
            return
        data = json.loads(response.text)
        terms = {'version': '', 'type': '', 'privacyUrl': '', 'termsOfUseUrl': '', 'title': ''}
        if data['status'] == 220:
            if data['message'] != "Utilizador deve aceitar a última versão dos consentimentos":
                logging.warning(f"Unusual message received: {data['message']}")
            terms.update(data['consents'])
        elif data['status'] == 200:
            pass
        else:
            logging.error(self.tr("Pingo Doce unknown login status: ") + f"{data['status']} / {data['message']}")
            return
        login_data = '{"phoneNumber":"' + self.phone_number + '","password":"' + self.ui.PasswordEdit.text() \
                     + '","consents":' + json.dumps(terms) + '}'
        response = self.web_session.post("https://app-proxy.pingodoce.pt/api/v2/identity/onboarding/login",
                                         data=login_data)
        if response.status_code != 200:
            logging.error(self.tr("Pingo Doce login failed: ") + f"{response.status_code}/{response.text}")
            return
        logging.info(self.tr("Pingo Doce login successful: ") + f"{response.text}")
        json_content = json.loads(response.text)
        try:
            assert json_content['token']['token_type'] == "Bearer"
            access_token = json_content['token']['access_token']
            refresh_token = json_content['token']['refresh_token']
            user_profile = json_content['profile']
            settings = JalSettings()
            settings.setValue('PtPingoDoceAccessToken', access_token)
            settings.setValue('PtPingoDoceRefreshToken', refresh_token)
            settings.setValue('PtPingoDoceUserProfile', json.dumps(user_profile))
            self.accept()
        except KeyError as e:
            logging.error(self.tr("Pingo Doce login response failed with: ") + e)
            return
