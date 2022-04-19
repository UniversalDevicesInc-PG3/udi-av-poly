import logging
import udi_interface
import os
import asyncore
from copy import deepcopy, copy
from threading import Thread
from av_funcs import get_server_data, get_profile_info
from nodes.node_factory import NodeFactory

"""
polyinterface has a LOGGER that is created by default and logs to:
logs/debug.log
You can use LOGGER.info, LOGGER.warning, LOGGER.debug, LOGGER.error levels as needed.
"""
LOGGER = udi_interface.LOGGER
Custom = udi_interface.Custom

DEFAULT_SHORT_POLL = 10
DEFAULT_LONG_POLL = 30
DEFAULT_DEBUG_MODE = 0


class AVController(udi_interface.Node, NodeFactory.SsdpListener):
    """
    The Controller Class is the primary node from an ISY perspective. It is a Superclass
    of polyinterface.Node so all methods from polyinterface.Node are available to this
    class as well.

    Class Variables:
    self.nodes: Dictionary of nodes. Includes the Controller node. Keys are the node addresses
    self.name: String name of the node
    self.address: String Address of Node, must be less than 14 characters (ISY limitation)
    self.polyConfig: Full JSON config dictionary received from Polyglot for the controller Node
    self.added: Boolean Confirmed added to ISY as primary node
    self.config: Dictionary, this node's Config

    Class Methods (not including the Node methods):
    start(): Once the NodeServer config is received from Polyglot this method is automatically called.
    addNode(polyinterface.Node, update = False): Adds Node to self.nodes and polyglot/ISY. This is called
        for you on the controller itself. Update = True overwrites the existing Node data.
    updateNode(polyinterface.Node): Overwrites the existing node data here and on Polyglot.
    delNode(address): Deletes a Node from the self.nodes/polyglot and ISY. Address is the Node's Address
    longPoll(): Runs every longPoll seconds (set initially in the server.json or default 10 seconds)
    shortPoll(): Runs every shortPoll seconds (set initially in the server.json or default 30 seconds)
    query(): Queries and reports ALL drivers for ALL nodes to the ISY.
    getDriver('ST'): gets the current value from Polyglot for driver 'ST' returns a STRING, cast as needed
    runForever(): Easy way to run forever without maxing your CPU or doing some silly 'time.sleep' nonsense
                  this joins the underlying queue query thread and just waits for it to terminate
                  which never happens.
    """

    def __init__(self, polyglot, primary, address, name):
        """
        Optional.
        Super runs all the parent class necessities. You do NOT have
        to override the __init__ method, but if you do, you MUST call super.
        """
        self.poly = polyglot
        self.ready = False
        self.serverData = get_server_data(LOGGER)
        self.l_info("init", "Initializing A/V NodeServer version %s" % str(self.serverData["version"]))
        self.hb = 0
        self.profile_info = None
        self.update_profile = False
        super().__init__(polyglot, primary, address, name)
        self.name = "AV Controller"
        self.primary = self.address
        self._nodeFactory = NodeFactory(self, self) # FIXME?
        self._stopAsyncLoop = False
        self._asyncStop = AsyncoreStop(self._stopAsyncLoop)
        self._asyncoreThread = Thread(name="AV Async Core", target=self._asyncore_loop)

        self.CustomParams = Custom(polyglot, 'customparams')

        polyglot.subscribe(polyglot.START, self.start, address)
        polyglot.subscribe(polyglot.POLL, self.poll)
        polyglot.subscribe(polyglot.CUSTOMPARAMS, self.parameterHandler)

        self.poly.ready()
        self.poly.addNode(self, conn_status="ST")

    def parameterHandler(self, params):
        self.CustomParams.load(params)

    def start(self):
        """
        Optional.
        Polyglot v2 Interface startup done. Here is where you start your integration.
        This will run, once the NodeServer connects to Polyglot and gets it's config.
        In this example I am calling a discovery method. While this is optional,
        this is where you should start. No need to Super this method, the parent
        version does nothing.
        """
        self.l_info("start", "Starting A/V NodeServer version %s" % str(self.serverData["version"]))
        self._nodeFactory.start_ssdp_listener()
        self.poly.updateProfile()
        self.poly.setCustomParamsDoc()

        self.setDriver("GV1", self.serverData["version_major"])
        self.setDriver("GV2", self.serverData["version_minor"])
        self.setDriver("ST", 1)
        self.reportDrivers()

        self._asyncoreThread.start()
        self.discover()

    def discover(self, *args, **kwargs):
        """
        Example
        Do discovery here. Does not have to be called discovery. Called from example
        controller start method and from DISCOVER command received from ISY as an exmaple.
        """

        # Add missing nodes
        param_devices = self._nodeFactory.load_params()
        self.l_debug("discover", "Parameter Device Count = {}".format(len(param_devices)))
        for k, v in param_devices.items():
            if not self.poly.getNode(k):
                self.add_node(address=k, device_type=v["type"], name=v["name"], host=v["host"], port=v["port"])

        self.set_device_count(len(self.poly.getNodes()))

        self._nodeFactory.ssdp_search()
        self.ready = True

    def on_new_ssdp_node(self, node):
        if not self.poly.getNodes(node.address):
            self.l_debug("on_new_ssdp_node", "Adding new node")
            self.l_debug("on_new_ssdp_node", node)
            self.poly.addNode(node)
            self.set_device_count(len(self.poly.getNodes()))

    def poll(self, pollflag):
        """
        Optional.
        This runs every 60 seconds. You would probably update your nodes either here
        or shortPoll. No need to Super this method the parent version does nothing.
        The timer can be overridden in the server.json.
        """
        if 'longPoll' in pollflag:
            self.heartbeat()

    def heartbeat(self):
        if self.hb is None or self.hb == 0:
            self.hb = 1
        else:
            self.hb = 0
        self.setDriver("GV4", self.hb)

    def query(self):
        """
        Optional.
        By default a query to the control node reports the FULL driver set for ALL
        nodes back to ISY. If you override this method you will need to Super or
        issue a reportDrivers() to each node manually.
        """
        super().query()

    def delete(self):
        """
        Example
        This is sent by Polyglot upon deletion of the NodeServer. If the process is
        co-resident and controlled by Polyglot, it will be terminated within 5 seconds
        of receiving this message.
        """
        LOGGER.info("Oh God I\"m being deleted. Nooooooooooooooooooooooooooooooooooooooooo.")

    def stop(self):
        self._asyncStop.stop()
        self._asyncoreThread.join()
        for n in self.poly.nodes():
            n.stop()
        self._nodeFactory.shutdown_ssdp_listener()

        LOGGER.debug("A/V NodeServer stopped.")

    def set_device_count(self, count):
        self.setDriver("GV3", (count - 1))

    def add_node(self, address, device_type, name, host, port):
        """
        Add a node that doesn't exist in either the config or controller
        :param address:
        :param device_type:
        :param name:
        :param host:
        :param port:
        :return:
        """
        node = self._nodeFactory.build(self.poly, address=address, device_type=device_type, name=name, host=host, port=port)
        if node is not None:
            self.l_debug("add_node", "Adding node: {}, Address: {}, Host: {}, Port: {}"
                         .format(node.name, node.address, node.host, node.port))
            self.poly.addNode(node)

        return node

    @staticmethod
    def hextoint(s):
        return int(s, 16)

    def l_info(self, name, string):
        LOGGER.info("%s:%s: %s" % (self.id, name, string))

    def l_error(self, name, string):
        LOGGER.error("%s:%s: %s" % (self.id, name, string))

    def l_warning(self, name, string):
        LOGGER.warning("%s:%s: %s" % (self.id, name, string))

    def l_debug(self, name, string):
        LOGGER.debug("%s:%s: %s" % (self.id, name, string))

    """
    Command Functions
    """
    def _asyncore_loop(self):
        self.l_info("_asyncore_loop", "Starting asyncore loop thread")
        while True:
            try:
                asyncore.loop(2, True)
            except asyncore.ExitNow:
                for channel in copy(asyncore.socket_map).values():
                    channel.handle_close()
                break
        self.l_info("_asyncore_loop", "Ending asyncore loop thread")

    """
    Optional.
    Since the controller is the parent node in ISY, it will actual show up as a node.
    So it needs to know the drivers and what id it will use. The drivers are
    the defaults in the parent Class, so you don't need them unless you want to add to
    them. The ST and GV1 variables are for reporting status through Polyglot to ISY,
    DO NOT remove them. UOM 2 is boolean.
    """
    id = "avController"
    commands = {
        "DISCOVER": discover,
    }
    drivers = [
        {"driver": "ST", "value": 0, "uom": 2},
        {"driver": "GV1", "value": 0, "uom": 56},   # vmaj: Version Major
        {"driver": "GV2", "value": 0, "uom": 56},   # vmin: Version Minor
        {"driver": "GV3", "value": 0, "uom": 56},   # device count
        {"driver": "GV4", "value": 0, "uom": 25},   # heartbeat
    ]


class AsyncoreStop(asyncore.file_dispatcher):
    def __init__(self, event_to_raise):
        self._eventToRaise = event_to_raise
        self._in_fd, self._out_fd = os.pipe()
        self._pipe = asyncore.file_wrapper(self._in_fd)
        super().__init__(self._pipe)

    def writable(self):
        return False

    def handle_close(self):
        os.close(self._out_fd)
        super().close()

    def handle_read(self):
        self.recv(64)
        self.handle_close()
        raise asyncore.ExitNow("Signal asyncore loop to exit")

    def stop(self):
        os.write(self._out_fd, b"stop")
