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

    # 'expected_errors' lists the HTTP status codes that are an ANSWER rather than a failure for this request, and are
    # therefore logged as debug instead of as an error. An API asked "do you know this transaction?" replies 404 for
    # every transaction it does not, and a caller that asks about many of them would otherwise fill the log the user
    # reads with red lines that say nothing went wrong. The result is '' either way - an expected error is still no data.
    def __init__(self, operation, url, params=None, headers=None, binary=False, expected_errors=()):
        super().__init__()
        self._mutex = QMutex()
        self._data = ''
        self._status = 0
        self._operation = operation
        self._url = url
        self._params = params
        self._headers = headers
        self._binary = binary
        self._expected_errors = expected_errors
        if not self.isRunning():
            self.start()

    def run(self):
        self._mutex.lock()
        url = self._url
        operation = self._operation
        params = self._params
        headers = self._headers
        binary = self._binary
        expected_errors = self._expected_errors
        self._mutex.unlock()
        status, result = self._request(operation, url, params=params, headers=headers, binary=binary,
                                       expected_errors=expected_errors)
        self._mutex.lock()
        self._data = result
        self._status = status
        self._mutex.unlock()

    def data(self):
        self._mutex.lock()
        data = self._data
        self._mutex.unlock()
        return data

    # HTTP status code the server answered with. It is 0 if no answer was received at all (timeout, no connection),
    # which lets a caller tell "the server says there is no such thing" from "nobody was asked" - the result is ''
    # in both cases, but only the first one is an answer worth remembering.
    def status(self) -> int:
        self._mutex.lock()
        status = self._status
        self._mutex.unlock()
        return status

    def _request(self, operation, url, params=None, headers=None, binary=False, expected_errors=()):
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
            return 0, ''
        except ConnectionError as e:
            logging.error(self.tr("Error") + ", URL {url}\n{e}")
            return 0, ''
        if response.status_code == 200:
            if binary:
                return response.status_code, response.content
            else:
                return response.status_code, response.text
        elif response.status_code in expected_errors:
            logging.debug(f"Expected [{response.status_code}] URL {url}\n{response.text}")
            return response.status_code, ''
        else:
            logging.error(self.tr("Failed") + f" [{response.status_code}] URL {url}\n{response.text}")
            return response.status_code, ''
