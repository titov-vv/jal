import logging
import platform
from enum import auto
import requests
from requests.exceptions import Timeout, RequestException
from PySide6.QtCore import QThread, QMutex, QDeadlineTimer
from jal import __version__


# Class that executes web-requests in a separate thread
# Request parameters are given in constructor and execution starts immediately after object creation
# Result of execution is available via data() method after thread completion
class WebRequest(QThread):
    GET = auto()        # Execute HTTP GET method
    POST = auto()       # Execute HTTP POST method with application/x-www-form-urlencoded
    POST_JSON = auto()  # Execute HTTP POST with JSON

    # Time limits of a single request, in seconds. Otherwise, it can hang forever is server "misbehaves".
    CONNECT_TIMEOUT = 30
    # The read limit is the gap allowed BETWEEN received chunks rather than the total duration, so a large but
    # progressing download is not cut off by it.
    READ_TIMEOUT = 60

    # How long wait() blocks by default: the length of one slice of a caller's waiting loop, not of a whole request.
    # A request has no completion callback, so every caller polls for it while keeping the GUI alive; polling without
    # blocking at all spins the CPU, while blocking for the whole request freezes the window.
    # One slice costs nothing and still lets the window repaint 20 times a second.
    POLL_INTERVAL_MS = 50
    # Deadline for a caller that wants the actual end of the request and has nothing to do meanwhile - see wait()
    FOREVER = QDeadlineTimer.Forever

    # Every request that has been started and hasn't been seen to finish yet.
    # A request that its caller gave up on - a cancelled download, an import that failed, a wallet fetch the user
    # stopped - can neither be stopped nor dropped: run() blocks inside 'requests' and has no event loop for quit()
    # to end, and destroying a running QThread aborts the whole application. The only safe end for such a request is
    # to let it finish by itself, which is what this list is for. It keeps the object alive meanwhile, and
    # wait_for_all() lets the application wait for the last of them instead of aborting on the way out.
    # Requests are created from the GUI thread only, so a plain list needs no protection of its own.
    _running_requests = []

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
        # Requests that have ended are forgotten here rather than by the thread that ends them: run() executes in the
        # request's own thread and must not touch a list the GUI thread reads. Nothing is lost by the delay - whoever
        # asked for a request holds it by itself for as long as it needs the answer.
        WebRequest._running_requests = [x for x in WebRequest._running_requests if x.isRunning()]
        WebRequest._running_requests.append(self)
        if not self.isRunning():
            self.start()

    # Waits for every request that is still running, and must be called before the application quits - a QThread
    # destroyed while running aborts the process. It is idempotent and cheap when there is nothing to wait for,
    # so it is called both on the way out of the main window and from QApplication.aboutToQuit, which also covers
    # the ways out that never close a window.
    @classmethod
    def wait_for_all(cls) -> None:
        for request in cls._running_requests:
            request.wait(cls.FOREVER)
        cls._running_requests = []

    def run(self):
        self._mutex.lock()
        url = self._url
        operation = self._operation
        params = self._params
        headers = self._headers
        binary = self._binary
        expected_errors = self._expected_errors
        self._mutex.unlock()
        # Nothing may leave run(): an exception thrown out of a Python override of QThread::run() is reported by
        # PySide to stderr and nowhere else - it never reaches the log window the user actually reads - and it
        # leaves the result at its initial value, which the caller can't tell from a request that returned nothing.
        # _request() already answers every failure it expects with (0, ''); this covers the ones it doesn't.
        try:
            status, result = self._request(operation, url, params=params, headers=headers, binary=binary,
                                           expected_errors=expected_errors)
        except Exception as e:
            logging.error(self.tr("Request failed") + f", URL {url}\n{e}")
            status, result = 0, ''
        self._mutex.lock()
        self._data = result
        self._status = status
        self._mutex.unlock()

    # Waits for the request to finish, returning True if it did and False if the deadline ran out first.
    # QThread.wait() waits forever unless told otherwise; here the default is one POLL_INTERVAL_MS slice instead,
    # because that is what every caller wants of it - a waiting loop that processes GUI events between the slices:
    #     while not request.wait():
    #         QApplication.processEvents()
    # Pass WebRequest.FOREVER to wait for the real end of the request (nothing is processed meanwhile).
    def wait(self, deadline=POLL_INTERVAL_MS) -> bool:
        return super().wait(deadline)

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
        timeout = (self.CONNECT_TIMEOUT, self.READ_TIMEOUT)
        try:
            if operation == WebRequest.GET:
                response = session.get(url, params=params, timeout=timeout)
            elif operation == WebRequest.POST:
                response = session.post(url, data=params, timeout=timeout)
            elif operation == WebRequest.POST_JSON:
                response = session.post(url, json=params, timeout=timeout)
            else:
                assert False
        except Timeout:
            logging.error(self.tr("Timeout") + f" URL {url}")
            return 0, ''
        # Every error 'requests' raises by design derives from RequestException - a refused or dropped connection,
        # a TLS failure, too many redirects, a malformed url. They are all "no answer was received", which is what
        # a status of 0 stands for.
        except RequestException as e:
            logging.error(self.tr("Error") + f", URL {url}\n{e}")
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
