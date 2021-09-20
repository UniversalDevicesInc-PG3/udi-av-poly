import udi_interface
import logging
import asyncore
import struct
from queue import PriorityQueue, Queue
import time
from enum import unique, Enum
from threading import Thread, Event, Condition, Lock
from av_devices.av_device import AvDevice


LOGGER = udi_interface.LOGGER


@unique
class Type(Enum):
    CONTROL = "C"
    ENQUIRY = "E"
    ANSWER = "A"
    NOTIFY = "N"


@unique
class Answer(Enum):
    # Fill out to 16 characters
    SUCCESS = "0" * 16
    ERROR = "F" * 16
    NOT_FOUND = "N" * 16


@unique
class Functions(Enum):
    IRCC_CODE = "IRCC"
    POWER_STATUS = "POWR"
    VOLUME = "VOLU"
    MUTE = "AMUT"
    SET_CHANNEL = "CHNN"
    TRIPLET_CHANNEL = "TCHN"
    INPUT_SOURCE = "ISRC"
    INPUT = "INPT"
    PICTURE_MUTE = "PMUT"
    TOGGLE_PICTURE_MUTE = "TPMU"
    PIP = "PIPI"
    TOGGLE_PIP = "TPIP"
    TOGGLE_PIP_POSITION = "TPPP"


@unique
class IrccCommands(Enum):
    POWER_OFF = 0
    INPUT = 1
    GGUIDE = 2
    EPG = 3
    FAVORITES = 4
    DISPLAY = 5
    HOME = 6
    OPTIONS = 7
    RETURN = 8
    UP = 9
    DOWN = 10
    RIGHT = 11
    LEFT = 12
    CONFIRM = 13
    RED = 14
    GREEN = 15
    YELLOW = 16
    BLUE = 17
    NUM1 = 18
    NUM2 = 19
    NUM3 = 20
    NUM4 = 21
    NUM5 = 22
    NUM6 = 23
    NUM7 = 24
    NUM8 = 25
    NUM9 = 26
    NUM0 = 27
    NUM11 = 28
    NUM12 = 29
    VOLUME_UP = 30
    VOLUME_DOWN = 31
    MUTE = 32
    CHANNEL_UP = 33
    CHANNEL_DOWN = 34
    SUBTITLE = 35
    CLOSED_CAPTION = 36
    ENTER = 37
    DOT = 38
    ANALOG = 39
    TELETEXT = 40
    EXIT = 41
    ANALOG2 = 42
    AD = 43
    DIGITAL = 44
    ANALOG_ = 45
    BS = 46
    CS = 47
    BS_CS = 48
    DDATA = 49
    PIC_OFF = 50
    TV_RADIO = 51
    THEATER = 52
    SEN = 53
    INTERNET_WIDGETS = 54
    INTERNET_VIDEO = 55
    NETFLIX = 56
    SCENE_SELECT = 57
    MODE3D = 58
    IMANUAL = 59
    AUDIO = 60
    WIDE = 61
    JUMP = 62
    PAP = 63
    MYEPG = 64
    PROGRAM_DESCRIPTION = 65
    WRITE_CHAPTER = 66
    TRACK_ID = 67
    TEN_KEY = 68
    APPLICAST = 69
    AC_TVILA = 70
    DELETE_VIDEO = 71
    PHOTO_FRAME = 72
    TV_PAUSE = 73
    KEYPAD = 74
    MEDIA = 75
    SYNC_MENU = 76
    FORWARD = 77
    PLAY = 78
    REWIND = 79
    PREV = 80
    STOP = 81
    NEXT = 82
    REC = 83
    PAUSE = 84
    EJECT = 85
    FLASH_PLUS = 86
    FLASH_MINUS = 87
    TOP_MENU = 88
    POPUP_MENU = 89
    RAKURAKU_START = 90
    ONE_TOUCH_TIME_RECORD = 91
    ONE_TOUCH_VIEW = 92
    ONE_TOUCH_RECORD = 93
    ONE_TOUCH_STOP = 94
    DUX = 95
    FOOTBALL_MODE = 96
    SOCIAL = 97

    def __new__(cls, v):
        obj = object.__new__(cls)
        # Zero pad
        obj._value_ = v
        obj.code = str(v).zfill(16)
        return obj

    @classmethod
    def get_by_value(cls, value):
        if isinstance(value, str):
            value = int(value)
        for name, member in cls.__members__.items():
            if member.value == value:
                return member
        else:
            raise ValueError


@unique
class Inputs(Enum):
    TV = 0, (0, 0)
    HDMI1 = 1, (1, 1)
    HDMI2 = 2, (1, 2)
    HDMI3 = 3, (1, 3)
    HDMI4 = 4, (1, 4)
    COMPOSITE = 5, (3, 1)
    COMPONENT = 6, (4, 1)
    SCREEN_MIRROR = 7, (5, 1)
    NETFLIX = 8, (0, IrccCommands.NETFLIX.value)
    UNKNOWN = 999, (-1, -1)

    def __new__(cls, keycode, param):
        obj = object.__new__(cls)
        # Build parameter to send to device
        obj._value_ = keycode
        obj.code = str(param[0]).zfill(8) + str(param[1]).zfill(8)
        return obj

    @classmethod
    def get_by_code(cls, code):
        if not isinstance(code, str):
            code = str(code).zfill(16)
        elif isinstance(code, str) and len(code) != 16:
            code = code.zfill(16)

        for name, member in cls.__members__.items():
            if member.code == code:
                return member
        else:
            return cls.UNKNOWN

    @classmethod
    def get_by_value(cls, value):
        if isinstance(value, str):
            value = int(value)
        for name, member in cls.__members__.items():
            if member.value == value:
                return member
        else:
            return cls.UNKNOWN


class CommData(object):
    MSGLEN = 24
    _commData = struct.Struct("2sc4s16sc")
    _header = b"*S"
    _footer = bytes([0x0a])

    def __init__(self, ctype=Type.CONTROL, function="", parameter="", pause=0):
        self._lock = Lock()
        self.pause = pause
        with self._lock:
            self.ctype = ctype.value
            if function == "":
                self.function = "#" * 16
            else:
                self.function = function
            if parameter == "":
                self.parameter = "#" * 16
            else:
                self.parameter = parameter

    def set_power(self, on_off=False):
        with self._lock:
            self.function = Functions.POWER_STATUS.value
            self.parameter = ("1" if on_off else "0").zfill(16)
            return self

    def get_power(self):
        with self._lock:
            self.ctype = Type.ENQUIRY.value
            self.function = Functions.POWER_STATUS.value
            return self

    def set_mute(self, on_off):
        with self._lock:
            self.function = Functions.MUTE.value
            self.parameter = ("1" if on_off else "0").zfill(16)
            return self

    def get_mute(self):
        with self._lock:
            self.ctype = Type.ENQUIRY.value
            self.function = Functions.MUTE.value
            return self

    def set_volume(self, volume):
        with self._lock:
            self.function = Functions.VOLUME.value
            self.parameter = volume.zfill(16)
            return self

    def get_volume(self):
        with self._lock:
            self.ctype = Type.ENQUIRY.value
            self.function = Functions.VOLUME.value
            return self

    def volume_up(self):
        with self._lock:
            self.function = Functions.IRCC_CODE.value
            self.parameter = IrccCommands.VOLUME_UP.value
            return self

    def volume_down(self):
        with self._lock:
            self.function = Functions.IRCC_CODE.value
            self.parameter = IrccCommands.VOLUME_DOWN.value
            return self

    def set_input(self, input_value):
        with self._lock:
            self.function = Functions.INPUT.value
            self.parameter = Inputs.get_by_value(input_value).code
#            self.parameter = Inputs[int(input_value)].code
            return self

    def get_input(self):
        with self._lock:
            self.ctype = Type.ENQUIRY.value
            self.function = Functions.INPUT.value
            return self

    def do_ircc(self, code):
        with self._lock:
            self.function = Functions.IRCC_CODE.value
            self.parameter = IrccCommands.get_by_value(code).code
            return self

    def pack(self):
        with self._lock:
            return self._commData.pack(
                    self._header, self.ctype.encode(), self.function.encode(), self.parameter.encode(), self._footer)

    def unpack(self, data):
        with self._lock:
            self._header, self.ctype, self.function, self.parameter, self._footer = self._commData.unpack(data)
            self.ctype = self.ctype.decode()
            self.function = self.function.decode()
            self.parameter = self.parameter.decode()
            return self


class ClientHandler(asyncore.dispatcher):
    class Listener(object):
        def on_connection_handler_response(self, data):
            pass

        def on_connection_closed(self):
            pass

        def on_connection_error(self, error):
            pass

    def __init__(self, host, port, logger, listener=None):
        self._lock = Lock()
        self.logger = logger
        self._host = host
        self._port = port
        self._stopThread = Event()
        self._sendQ = PriorityQueue()
        self._waitForResponseQ = Queue()
        self._writeBuffer = []
        self._listeners = []
        if listener is not None:
            self._listeners.append(listener)
        self._closed = True
        super().__init__()

    def add_listener(self, listener):
        self._listeners.append(listener)

    def set_closed(self, value):
        self._closed = value

    def is_closed(self):
        return self._closed

    def handle_connect(self):
        self.logger.info("Sony Bravia: Connected")
        self.set_closed(False)

    def handle_close(self):
        if not self.is_closed():
            self.close()
            self.logger.info("Sony Bravia: Disconnected")
            self.set_closed(True)

    def writable(self):
        return (len(self._writeBuffer) > 0 or not self._sendQ.empty()) and self._waitForResponseQ.empty()

    def readable(self):
        return True

    def handle_read(self):
        received = self.recv(CommData.MSGLEN)
        if received == b"":
            for l in self._listeners:
                l.on_connection_closed()
            return

        self.logger.debug("Sony Bravia: <-- Raw: {}".format(received))
        data = CommData().unpack(received)
        if data.ctype == Type.ANSWER.value:
            if not self._waitForResponseQ.empty():
                self._waitForResponseQ.get()
                self._waitForResponseQ.task_done()

        for l in self._listeners:
            l.on_connection_handler_response(data)

    def handle_write(self):
        if len(self._writeBuffer) > 0:
            data = self._writeBuffer.pop()
        else:
            _, data = self._sendQ.get()
            if data.pause > 0:
                time.sleep(data.pause)

            # Need to stash this so we can check for a response in the reader
            self._waitForResponseQ.put(data)
            data = data.pack()
            self.logger.debug("Sony Bravia: --> Raw: {}".format(data))

        sent = self.send(data)
        if sent < len(data):
            remaining = data[sent:]
            self._writeBuffer.append(remaining)
        else:
            self._sendQ.task_done()

    def start(self):
        try:
            self.logger.debug("Sony Bravia: Connecting")
            self.create_socket()
            self.connect((self._host, self._port))
        except Exception as e:
            self.logger.exception("Sony Bravia: Connection handler error while connecting: {}".format(e))
            raise

    def stop(self):
        self.handle_close()

    def send_command(self, data):
        self.logger.debug("Sony Bravia: Queueing Request: {}".format(data.pack()))
        qdata = (time.time(), data)
        self._sendQ.put(qdata)


class SonyBraviaXBR65X810CDevice(AvDevice, ClientHandler.Listener):
    INPUTS = {name: member.value for name, member in Inputs.__members__.items()}
    INVERTED_INPUTS = {member.value: name for name, member in Inputs.__members__.items()}
    DEAD_THREAD = Thread()

    def __init__(self, name, ip, port=20060, logger=None):
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger()
        super().__init__(name, logger)
        self._ip = ip
        self._port = port
        self._sentQ = PriorityQueue()
        self._connectionHandler = ClientHandler(self._ip, int(self._port), self.logger, self)

    def connect(self):
        if self._connectionHandler is None:
            self._connectionHandler = ClientHandler(self._ip, int(self._port), self.logger, self)
        self._connectionHandler.start()

    def disconnect(self):
        if self._connectionHandler is not None:
            self._connectionHandler.stop()
            self._connectionHandler = None

    def initialize_state(self):
        self.query()
        time.sleep(1)

    "Turn device on/off"""
    def set_power(self, turn_on, pause=0):
        self._send(CommData(pause=pause).set_power(turn_on))

    "Mute/Unmute sound"""
    def set_mute(self, mute_on, pause=0):
        self._send(CommData(pause=pause).set_mute(mute_on))

    "Set volume to specific value on 0-100 scale"""
    def set_volume(self, volume, pause=0):
        self._send(CommData(pause=pause).set_volume(volume))

    "Send request to increment volume by 1 unit"""
    def volume_up(self, pause=0):
        self._send(CommData(pause=pause).volume_up())

    "Send request to decrease volume by 1 unit"""
    def volume_down(self, pause=0):
        self._send(CommData(pause=pause).volume_down())

    "Send request to change input selector"""
    def set_input(self, input_value, pause=0):
        if int(input_value) >= Inputs.NETFLIX.value:
            self.do_ircc(Inputs.get_by_value(input_value).code, pause=pause)
        else:
            self._send(CommData(pause=pause).set_input(input_value))

    "Send IRCC request"""
    def do_ircc(self, code, pause=0):
        if isinstance(code, IrccCommands):
            self._send(CommData(pause=pause).do_ircc(code.value))
        else:
            self._send(CommData(pause=pause).do_ircc(code))

    def query_power(self, pause=0):
        self._send(CommData(Type.ENQUIRY, pause=pause).get_power())

    def query_volume(self, pause=0):
        self._send(CommData(Type.ENQUIRY, pause=pause).get_volume())

    def query_input(self, pause=0):
        self._send(CommData(Type.ENQUIRY, pause=pause).get_input())

    def query_mute(self, pause=0):
        self._send(CommData(Type.ENQUIRY, pause=pause).get_mute())

    def query(self):
        self.query_power()
        self.query_volume()
        self.query_mute()
        self.query_input()

    def on_connection_handler_response(self, data):
        self._update_states(data)

    def on_connection_closed(self):
        self.handle_error(error=AvDevice.Error("Sony Bravia: Connection closed"))

    def on_connection_error(self, error):
        self.handle_error(error=AvDevice.Error("Sony Bravia: Connection error"))

    def _update_states(self, comm):
        for l in self.listeners:
            l.on_responding()

        if comm.ctype != Type.ANSWER.value and comm.ctype != Type.NOTIFY.value:
            self.logger.error("Sony Bravia: Response not an Answer or Notify type")
            return

        # Retrieve data that we sent
        if comm.ctype == Type.ANSWER.value:
            _, data_sent = self._sentQ.get()
            self._sentQ.task_done()

            # Some success messages can be ignored since we'll get a notification of the change
            if data_sent.ctype == Type.CONTROL.value and comm.parameter == Answer.SUCCESS.value:
                # We don't get a notification from an "input" change if we have loaded an app (i.e. NetFlix)
                # and then set the input back to the same value in order to exit the app
                if comm.function == Functions.INPUT.value:
                    self.input = Inputs.get_by_code(data_sent.parameter).value

                # If an IRCC code is sent successfully, an app may have been loaded.  In that case, we want to
                # query the input mode so the value gets updated
                if comm.function == Functions.IRCC_CODE.value:
                    self.query_input(pause=2)
                return

        if comm.parameter == Answer.NOT_FOUND.value:
            self.logger.error("Sony Bravia: Response: Not Found")
            return

        command = comm.function
        if comm.ctype == Type.ANSWER.value and comm.parameter == Answer.ERROR.value:
            if command == Functions.INPUT.value:
                self.input = int(Inputs.UNKNOWN.value)
            elif command == Functions.VOLUME.value:
                self.volume = 0
            elif command == Functions.MUTE.value:
                self.mute = False
            else:
                self.logger.error("Sony Bravia: Response error received")
            return

        if command == Functions.POWER_STATUS.value:
            self.power = int(comm.parameter) == 1
            if self.power:
                self.query_input()
            else:
                self.mute = False
                self.volume = 0
                self.input = Inputs.UNKNOWN.value
        elif command == Functions.MUTE.value:
            self.mute = int(comm.parameter)
        elif command == Functions.VOLUME.value:
            self.volume = int(comm.parameter)
        elif command == Functions.INPUT.value:
            v = Inputs.get_by_code(comm.parameter)
            if v is Inputs.UNKNOWN:
                self.logger.error("Sony Bravia: Returned unknown source value")
            self.input = v.value

    """Sends single command to AV"""
    def _send(self, data):
        if not self.is_running() or self._connectionHandler is None:
            return

        data_len = len(data.pack())
        if data_len != CommData.MSGLEN:
            self.logger.debug("Sony Bravia: Message data length({}) != to required {}".format(data_len, CommData.MSGLEN))
            return

        self._sentQ.put((time.time(), data))
        self._connectionHandler.send_command(data)
