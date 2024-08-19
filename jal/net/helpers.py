import os
import requests
from requests.exceptions import ConnectTimeout, ConnectionError
import logging
import platform
from PySide6.QtWidgets import QApplication
from jal import __version__
from jal.constants import Setup
from jal.db.settings import JalSettings


# ===================================================================================================================
# Retrieve URL from web with given method and params
def request_url(method, url, params=None, json_params=None, headers=None, binary=False, verify=True):
    session = requests.Session()
    session.headers['User-Agent'] = f"JAL/{__version__} ({platform.system()} {platform.release()})"
    if headers is not None:
        session.headers.update(headers)
    try:
        if method == "GET":
            response = session.get(url, params=params, verify=verify)
        elif method == "POST":
            if params:
                response = session.post(url, data=params, verify=verify)
            elif json_params:
                response = session.post(url, json=json_params, verify=verify)
            else:
                response = session.post(url, verify=verify)
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
def get_web_data(url, headers=None, binary=False, verify=True):
    if type(verify) != bool:  # there is a certificate path given -> add full path to it
        verify = JalSettings.path(JalSettings.PATH_APP) + Setup.NET_PATH + os.sep + verify
    return request_url("GET", url, headers=headers, binary=binary, verify=verify)


# ===================================================================================================================
# Function download URL and return it content as string or empty string if site returns error
def post_web_data(url, params=None, json_params=None, headers=None, binary=False):
    return request_url("POST", url, params=params, json_params=json_params, headers=headers, binary=binary)
