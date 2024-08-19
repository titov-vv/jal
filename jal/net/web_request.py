from enum import auto
from jal.net.helpers import request_url
from PySide6.QtCore import QThread, QMutex


# Class that executes web-requests in a separate thread
# Request parameters are given in constructor and execution starts immediately after object creation
# Status of execution may be checked with completed() method and received result is accessible via data() method
class WebRequest(QThread):
    GET = auto()        # Execute HTTP GET method
    POST = auto()       # Execute HTTP POST method with application/x-www-form-urlencoded
    POST_JSON = auto()  # Execute HTTP POST with JSON

    def __init__(self, operation, url, params=None, headers=None, binary=False):
        super().__init__()
        self._mutex = QMutex()
        self._data = None
        self._completed = False
        self._op = operation
        self._url = url
        self._params = params
        self._headers = headers
        self._binary = binary
        if not self.isRunning():
            self.start()

    def run(self):
        json = False
        self._mutex.lock()
        if self._op == self.GET:
            method = "GET"
        elif self._op == self.POST:
            method = "POST"
        else:
            method = "POST"
            json = True
        url = self._url
        params = self._params
        headers = self._headers
        binary = self._binary
        self._mutex.unlock()
        if json:
            result = request_url(method, url, json_params=params, headers=headers, binary=binary)
        else:
            result = request_url(method, url, params=params, headers=headers, binary=binary)
        self._mutex.lock()
        self._data = result
        self._completed = True
        self._mutex.unlock()

    def completed(self) -> bool:
        self._mutex.lock()
        completed = self._completed
        self._mutex.unlock()
        return completed

    def data(self):
        self._mutex.lock()
        data = self._data
        self._mutex.unlock()
        return data
