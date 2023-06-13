import uuid
import json
import logging
import requests
from PySide6.QtCore import QObject
from jal.net.helpers import get_web_data, post_web_data


#-----------------------------------------------------------------------------------------------------------------------
class SlipsTaxAPI(QObject):
    # Status codes that may be returned as result of class methods
    Failure = -1
    Success = 0
    Pending = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.slip_json = None
        self.web_session = requests.Session()
        self.web_session.headers['ClientVersion'] = '2.9.0'
        self.web_session.headers['Device-Id'] = str(uuid.uuid1())
        self.web_session.headers['Device-OS'] = 'Android'
        self.web_session.headers['Content-Type'] = 'application/json; charset=UTF-8'
        self.web_session.headers['Accept-Encoding'] = 'gzip'
        self.web_session.headers['User-Agent'] = 'okhttp/4.2.2'

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
