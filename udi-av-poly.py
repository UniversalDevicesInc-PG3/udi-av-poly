#!/usr/bin/env python3
"""
This is a NodeServer template for Polyglot v2 written in Python2/3
by Einstein.42 (James Milne) milne.james@gmail.com
"""
import udi_interface
import sys
from nodes import AVController

"""
Import the polyglot interface module. This is in pypy so you can just install it
normally. Replace pip with pip3 if you are using python3.

Virtualenv:
pip install udi_interface

Not Virutalenv:
pip install udi_interface --user

*I recommend you ALWAYS develop your NodeServers in virtualenv to maintain
cleanliness, however that isn't required. I do not condone installing pip
modules globally. Use the --user flag, not sudo.
"""

LOGGER = udi_interface.LOGGER
"""
udi_interface has a LOGGER that is created by default and logs to:
logs/debug.log
You can use LOGGER.info, LOGGER.warning, LOGGER.debug, LOGGER.error levels as needed.
"""


if __name__ == "__main__":
    try:
        polyglot = udi_interface.Interface([])
        """
        Instantiates the Interface to Polyglot.
        """
        polyglot.start()
        """
        Starts MQTT and connects to Polyglot.
        """
        AVController(polyglot, 'controller', 'controller', 'AVRECEIVER')
        """
        Creates the Controller Node and passes in the Interface
        """
        polyglot.runForever()
        """
        Sits around and does nothing forever, keeping your program running.
        """
    except (KeyboardInterrupt, SystemExit):
        """
        Catch SIGTERM or Control-C and exit cleanly.
        """
        sys.exit(0)
