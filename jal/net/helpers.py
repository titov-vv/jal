import requests
from requests.exceptions import ConnectTimeout, ConnectionError
import logging
import platform
from PySide6.QtWidgets import QApplication
from jal import __version__


# ===================================================================================================================
# Function returns custom User Agent for web requests
def make_user_agent(url='') -> str:
    if "www.cbr.ru" in url:
        return "curl/7.77.0"   # Workaround for DDoS-GUARD activation on www.cbr.ru
    else:
        return f"JAL/{__version__} ({platform.system()} {platform.release()})"


# ===================================================================================================================
# Returns true if text does contain only English alphabet
def isEnglish(text):
    try:
        text.encode(encoding='utf-8').decode(encoding='ascii')
    except UnicodeDecodeError:
        return False
    else:
        return True


# ===================================================================================================================
# Retrieve URL from web with given method and params
def request_url(method, url, params=None, json_params=None, headers=None, binary=False):
    session = requests.Session()
    session.headers['User-Agent'] = make_user_agent(url=url)
    if headers is not None:
        session.headers.update(headers)
    try:
        if method == "GET":
            response = session.get(url)
        elif method == "POST":
            if params:
                response = session.post(url, data=params)
            elif json_params:
                response = session.post(url, json=json_params)
            else:
                response = session.post(url)
        else:
            raise ValueError("Unknown download method for URL")
    except ConnectTimeout:
        logging.error(f"URL {url}\nConnection timeout.")
        return ''
    except ConnectionError as e:
        logging.error(f"URL {url}\nConnection error: {e}")
        return ''
    if response.status_code == 200:
        if binary:
            return response.content
        else:
            return response.text
    else:
        logging.error(f"URL: {url}" + QApplication.translate('Net', " failed: ")
                      + f"{response.status_code}: {response.text}")
        return ''


# ===================================================================================================================
# Function download URL and return it content as string or empty string if site returns error
def get_web_data(url, headers=None, binary=False):
    return request_url("GET", url, headers=headers, binary=binary)


# ===================================================================================================================
# Function download URL and return it content as string or empty string if site returns error
def post_web_data(url, params=None, json_params=None, headers=None, binary=False):
    return request_url("POST", url, params=params, json_params=json_params, headers=headers, binary=binary)
