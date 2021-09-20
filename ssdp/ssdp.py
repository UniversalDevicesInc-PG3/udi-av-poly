import udi_interface
import os
import socket
import select
import http.client
import io
from threading import Thread
from queue import PriorityQueue, Empty
import requests
import xmltodict

LOGGER = udi_interface.LOGGER


class SSDPResponse(object):
    class _FakeSocket(io.BytesIO):
        def makefile(self, *args, **kw):
            return self

    def __init__(self, response):
        r = http.client.HTTPResponse(self._FakeSocket(response))
        r.begin()

        self.info = {}
        self.manufacturer = None
        self.model = None
        self.location = r.getheader("location")
        self.usn = r.getheader("usn")
        self.st = r.getheader("st")
        self.cache = r.getheader("cache-control").split("=")[1]
        self.port = 80
        LOGGER.info("Location: {}".format(self.location))
        if "//" in self.location:
            splits = self.location.split("//")
            self.host = splits[1].split(":")[0]
            if ":" in splits[1]:
                self.port = splits[1].split(":")[1].split("/")[0]

    def __repr__(self):
        return "<SSDPResponse({location}, {st}, {usn}, {manufacturer}, {model})>".format(**self.__dict__)

    def add_info(self, info):
        self.info = info
        self.manufacturer = info["root"]["device"]["manufacturer"]
        self.model = info["root"]["device"]["modelName"]


class SSDP(object):
    class Listener(object):
        def on_ssdp_response(self, ssdp_response):
            pass

    def __init__(self, listener=None, timeout=10):
        self._listeners = []
        if listener is not None:
            self._listeners.append(listener)

        self._responseQueue = PriorityQueue()
        self._timeout = timeout
        self._listenThread = None
        self._responseThread = None
        self._sock = None
        self._queuePriority = 1
        self._rfd = 0
        self._wfd = 0

    def start(self):
        if self._listenThread is None:
            self._rfd, self._wfd = os.pipe()
            self._new_socket()
            self._listenThread = Thread(name="SSDP Listener", target=self._listen_thread)
            self._listenThread.start()
            self._responseThread = Thread(name="SSDP Response Handler", target=self._response_handler)
            self._responseThread.start()

    def add_listener(self, listener):
        if listener is not None:
            self._listeners.append(listener)

    def search(self, service, mx=3):
        if self._sock is not None:
            LOGGER.debug("Searching SSDP")
            group = ("239.255.255.250", 1900)
            message = "\r\n".join([
                'M-SEARCH * HTTP/1.1',
                'HOST: {0}:{1}',
                'MAN: "ssdp:discover"',
                'ST: {st}', 'MX: {mx}', '', ''])
            self._sock.sendto(message.format(*group, st=service, mx=mx).encode(), group)

    def shutdown(self):
        if self._listenThread is not None:
            os.write(self._wfd, b"exit\n")
            self._listenThread.join()
            self._listenThread = None
            os.close(self._wfd)
            os.close(self._rfd)
            self._sock.close()
            self._sock = None

        if self._responseThread is not None:
            self._responseQueue.put_nowait((0, "exit"))
            self._responseThread.join()
            self._responseThread = None

    def discover(self, service, timeout=None, retries=1, mx=3):
        if timeout is None:
            to = self._timeout
        else:
            to = timeout

        group = ("239.255.255.250", 1900)
        message = "\r\n".join([
            'M-SEARCH * HTTP/1.1',
            'HOST: {0}:{1}',
            'MAN: "ssdp:discover"',
            'ST: {st}', 'MX: {mx}', '', ''])
        responses = {}
        for _ in range(retries):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.settimeout(to)
            sock.sendto(message.format(*group, st=service, mx=mx).encode(), group)
            while True:
                try:
                    response = SSDPResponse(sock.recv(1024))
                    responses[response.location] = response
                except socket.timeout:
                    break
        return responses.values()

    def _new_socket(self):
        if self._sock is not None:
            self._sock.close()

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        self._sock.settimeout(self._timeout)

    def _response_handler(self):
        LOGGER.info("Starting SSDP response handler")
        while True:
            p, response = self._responseQueue.get()

            # A string object equal to "exit" will empty the queue and end the thread
            if isinstance(response, str) and response == "exit":
                self._responseQueue.task_done()
                self._empty_response_queue()
                break

            location = response.location
            try:
                r = requests.get(location)
                if r.status_code == 200:
                    response.add_info(xmltodict.parse(r.text))
                    for l in self._listeners:
                        l.on_ssdp_response(response)
                        self._responseQueue.task_done()
            except requests.ConnectionError as e:
                LOGGER.error("Failed to retrieve web service information for {}".format(location))
                LOGGER.error(e)

        LOGGER.info("Ending SSDP response handler")

    def _empty_response_queue(self):
        while True:
            try:
                self._responseQueue.get_nowait()
                self._responseQueue.task_done()
            except Empty:
                break

    def _listen_thread(self):
        LOGGER.info("Starting SSDP listener")
        while True:
            try:
                ready, _, _ = select.select([self._sock, self._rfd], [], [])
                if self._rfd in ready:
                    os.read(self._rfd, 1024)
                    break
                elif self._sock in ready:
                    response = SSDPResponse(self._sock.recv(1024))

                    # Some devices return no URL other than either host or host:port.  These tend to not return any
                    #  XML info when the location is looked up, so we will ignore them.
                    if "//" not in response.location:
                        continue
                    sv = response.location.split("//")
                    if "/" not in sv[1]:
                        continue

                    self._queuePriority += 1
                    self._responseQueue.put_nowait((self._queuePriority, response))

            except socket.error:
                break

        LOGGER.info("Ending SSDP listener")
