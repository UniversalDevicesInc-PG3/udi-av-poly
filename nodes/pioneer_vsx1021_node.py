import udi_interface
from .av_node import AVNode
from av_devices.av_device import AvDevice
from av_devices import PioneerVSX1021Device


LOGGER = udi_interface.LOGGER


class PioneerVSX1021Node(AVNode, AvDevice.Listener):
    TYPE = "VSX1021"

    def __init__(self, controller, primary, host, port, address=None, name=None):
        self.host = host
        self.port = port
        self.commands.update(self.vsx1021_commands)
        self.drivers.extend(self.vsx1021_drivers)
        super().__init__(controller, primary, address, name)
        self.client = PioneerVSX1021Device(self.TYPE + ":" + name, self.host, self.port, logger=LOGGER)
        self.client.add_listener(self)

    def start(self):
        self.client.start()
        self.client.wait_for_startup()
        self.setDriver(self.Drivers.DEVICE_TYPE, 1)
        self.reportDrivers()

    def stop(self):
        self.client.stop()
        self.reportDrivers()

    def query(self):
        self.client.query()

    def set_power(self, val):
        self.l_debug("set_power", "CMD Power: {}".format("True" if val else "False"))
        self.client.set_power(val == 1)

    def set_mute(self, val):
        self.l_debug("set_mute", "CMD Mute: {}".format("True" if val else "False"))
        self.client.set_mute(val == 1)

    def set_volume(self, val):
        self.l_debug("set_volume", "CMD Volume: {}".format(val))
        self.client.set_volume(float(val))

    def set_input(self, val):
        self.l_debug("set_source", "CMD Source: {}".format(PioneerVSX1021Device.INVERTED_INPUTS[str(val).zfill(2)]))
        self.client.set_input(val)

    def on_connected(self):
        self.setDriver(self.Drivers.STATUS, 1)

    def on_disconnected(self):
        self.setDriver(self.Drivers.STATUS, 0)

    def on_power(self, power_state):
        self.l_debug("on_power", "{}".format("True" if power_state else "False"))
        self.setDriver(self.Drivers.POWER, 1 if power_state else 0)

    def on_volume(self, volume):
        self.l_debug("on_volume", "{}".format(volume))
        self.setDriver(self.Drivers.VOLUME, self.client.volume)

    def on_mute(self, mute_state):
        self.l_debug("on_mute", "{}".format("True" if mute_state else "False"))
        self.setDriver(self.Drivers.MUTE, 1 if mute_state else 0)

    def on_input(self, input_value):
        self.l_debug("on_input", "{}".format(PioneerVSX1021Device.INVERTED_INPUTS[input_value]))
        self.setDriver(self.Drivers.INPUT, "{:0.1f}".format(float(input_value)))

    def on_responding(self):
        self.setDriver(self.Drivers.STATUS, 1)

    def on_not_responding(self):
        self.setDriver(self.Drivers.STATUS, 0)

    """
    Command Functions
    """
    def cmd_set_power(self, command):
        val = command.get("value")
        self.l_info("cmd_set_power", val)
        self.set_power(val == "1")

    def cmd_set_mute(self, command):
        val = command.get("value")
        self.l_info("cmd_set_mute", val)
        self.set_mute(val == "1")

    def cmd_set_volume(self, command):
        val = command.get("value")
        self.l_info("cmd_set_volume", val)
        self.set_volume(val)

    def cmd_set_input(self, command):
        val = command.get("value")
        self.l_info("cmd_set_input", val)
        if val != PioneerVSX1021Device.INPUTS["UNKNOWN"]:
            self.set_input(val)

    def setDriver(self, driver, value, report=True, force=False, uom=None):
        if isinstance(driver, str):
            super().setDriver(driver, value, report, force, uom)
        elif isinstance(driver, self.Drivers):
            super().setDriver(driver.value, value, report, force, uom)

    def l_info(self, name, string):
        LOGGER.info("%s:%s: %s" % (self.id, name, string))

    def l_error(self, name, string):
        LOGGER.error("%s:%s: %s" % (self.id, name, string))

    def l_warning(self, name, string):
        LOGGER.warning("%s:%s: %s" % (self.id, name, string))

    def l_debug(self, name, string):
        LOGGER.debug("%s:%s: %s" % (self.id, name, string))

    vsx1021_commands = {
        "SET_POWER": cmd_set_power,
        "SET_MUTE": cmd_set_mute,
        "SET_VOLUME": cmd_set_volume,
        "SET_INPUT": cmd_set_input
    }

    vsx1021_drivers = [
    ]
