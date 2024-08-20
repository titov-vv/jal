import logging
import platform
from enum import auto
import requests
from requests.exceptions import ConnectTimeout, ConnectionError
from PySide6.QtCore import QThread, QMutex
from jal import __version__


# Class that executes web-requests in a separate thread
# Request parameters are given in constructor and execution starts immediately after object creation
# Result of execution is available via data() method after thread completion
class WebRequest(QThread):
    GET = auto()        # Execute HTTP GET method
    POST = auto()       # Execute HTTP POST method with application/x-www-form-urlencoded
    POST_JSON = auto()  # Execute HTTP POST with JSON

    def __init__(self, operation, url, params=None, headers=None, binary=False):
        super().__init__()
        self._mutex = QMutex()
        self._data = ''
        self._operation = operation
        self._url = url
        self._params = params
        self._headers = headers
        self._binary = binary
        if not self.isRunning():
            self.start()

    def run(self):
        self._mutex.lock()
        url = self._url
        operation = self._operation
        params = self._params
        headers = self._headers
        binary = self._binary
        self._mutex.unlock()
        result = self._request(operation, url, params=params, headers=headers, binary=binary)
        self._mutex.lock()
        self._data = result
        self._mutex.unlock()

    def data(self):
        self._mutex.lock()
        data = self._data
        self._mutex.unlock()
        return data

    def _request(self, operation, url, params=None, headers=None, binary=False):
        session = requests.Session()
        session.headers['User-Agent'] = f"JAL/{__version__} ({platform.system()} {platform.release()})"
        if headers is not None:
            session.headers.update(headers)
        try:
            if operation == WebRequest.GET:
                response = session.get(url, params=params)
            elif operation == WebRequest.POST:
                response = session.post(url, data=params)
            elif operation == WebRequest.POST_JSON:
                response = session.post(url, json=params)
            else:
                assert False
        except ConnectTimeout:
            logging.error(self.tr("Timeout") + " URL {url}")
            return ''
        except ConnectionError as e:
            logging.error(self.tr("Error") + ", URL {url}\n{e}")
            return ''
        if response.status_code == 200:
            if binary:
                return response.content
            else:
                return response.text
        else:
            logging.error(self.tr("Failed") + f" [{response.status_code}] URL {url}\n{response.text}")
            return ''
