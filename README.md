# A/V NodeServer for PolyGlot V2

This is a generic A/V device node server for the [Universal Devices ISY Controller](https://www.universal-devices.com/residential/ISY)

(c) Brad Whitted
MIT License

## How it works

### User perspective:
This nodeserver supports multiple A/V devices, but only if they have been built into the code.  The supported devices
are listed below along with any required parameters needed to specify how to connect to them.  Each one is particular
to that device and will have different requirements.
   
### Supported Devices:
  1. Pioneer VSX-1021 (possibly other VSX series, but use the VSX1021 custom parameter to define them) receiver.
     
     Should be detected via SSDP discovery.  If it isn't, use the custom config parameter method to set it up.
  
     Custom config parameters:
     
       * VSX1021xxxx = Host IP and port of receiver, i.e. 192.168.1.xx:23
       
     Supported Commands
     
      * Power
      * Mute
      * Volume
      * Input
        * PHONO
        * CD
        * TUNER
        * CD-R/TAPE
        * DVD
        * TV/SAT
        * VIDEO1
        * MULTI CH IN
        * VIDEO2
        * DVR/BDR
        * IPOD/USB
        * XM RADIO
        * HDMI1
        * HDMI2
        * HDMI3
        * HDMI4
        * HDMI5
        * BD
        * HOME MEDIA GALLERY
        * SIRIUS
        * HDMI CYCLE
        * ADAPTER
       
  2. Sony Bravia XBR-65X810C (possibly other Bravia series, but use the BRAVIA custom parameter to define them) TV.  
     Be sure to have Simple IP Control turned on in your network settings on the TV.
     
     Should be detected via SSDP discovery.  If it isn't, use the custom config parameter method to set it up.
  
    Custom config parameters:

      * BRAVIAxxxx = Host IP and port of receiver, i.e. 192.168.1.xx:20060

    Supported Commands
     
      * Power
      * Mute
      * Volume
      * Input
        * TV
        * HDMI1
        * HDMI2
        * HDMI3
        * HDMI4
        * Composite
        * Component
        * Screen Mirror
        * NetFlix (This is a pseudo input.  It's really an IRCC command but I use it so much I handle it like
          a normal input)
      * IRCC Commands: Some of these didn't work, but are listed in the Sony Simple IP control docs.
        * POWER_OFF
        * INPUT
        * GGUIDE
        * EPG
        * FAVORITES
        * DISPLAY
        * HOME
        * OPTIONS
        * RETURN
        * UP
        * DOWN
        * RIGHT
        * LEFT
        * CONFIRM
        * RED
        * GREEN
        * YELLOW
        * BLUE
        * NUM1
        * NUM2
        * NUM3
        * NUM4
        * NUM5
        * NUM6
        * NUM7
        * NUM8
        * NUM9
        * NUM0
        * NUM11
        * NUM12
        * VOLUME_UP
        * VOLUME_DOWN
        * MUTE
        * CHANNEL_UP
        * CHANNEL_DOWN
        * SUBTITLE
        * CLOSED_CAPTION
        * ENTER
        * DOT
        * ANALOG
        * TELETEXT
        * EXIT
        * ANALOG2
        * AD
        * DIGITAL
        * ANALOG_
        * BS
        * CS
        * BS_CS
        * DDATA
        * PIC_OFF
        * TV_RADIO
        * THEATER
        * SEN
        * INTERNET_WIDGETS
        * INTERNET_VIDEO
        * NETFLIX
        * SCENE_SELECT
        * MODE3D
        * IMANUAL
        * AUDIO
        * WIDE
        * JUMP
        * PAP
        * MYEPG
        * PROGRAM_DESCRIPTION
        * WRITE_CHAPTER
        * TRACK_ID
        * TEN_KEY
        * APPLICAST
        * AC_TVILA
        * DELETE_VIDEO
        * PHOTO_FRAME
        * TV_PAUSE
        * KEYPAD
        * MEDIA
        * SYNC_MENU
        * FORWARD
        * PLAY
        * REWIND
        * PREV
        * STOP
        * NEXT
        * REC
        * PAUSE
        * EJECT
        * FLASH_PLUS
        * FLASH_MINUS
        * TOP_MENU
        * POPUP_MENU
        * RAKURAKU_START
        * ONE_TOUCH_TIME_RECORD
        * ONE_TOUCH_VIEW
        * ONE_TOUCH_RECORD
        * ONE_TOUCH_STOP
        * DUX
        * FOOTBALL_MODE
        * SOCIAL

SSDP will search the network for your devices (the devices should be on.  If they are off, then they might be missed).
If SSDP doesn't find your devices, then you can define custom parameters for it as indicated.  If defining custom
parameters, then you'll need to restart the nodeserver after they are defined.

### Installation
1. Backup Your ISY in case of problems!  **Really, do the backup, please**
2. Go to the Polyglot Store in the UI and install A/VServer.
4. Open Admin Console (if you already had it open, then close and re-open)
5. You should now have a node called AV Controller
6. Add appropriate custom parameters for your device if the SSDP searach didn't find them (see How it works above)
7. Restart the nodeserver if you added custom parameters

If you add more A/V devices after initial install/setup, just turn them on and then click the 'Discover' button on the
controller page to force an SSDP search.  If you have to add custom parameters, then a restart of the nodeserver
will be required.

### Requirements
1. A Polisy running Polyglot V3
2. This has only been tested with ISY 5.3.x or later
3. A support Pioneer or Sony device

### Developer perspective:
This nodeserver is built on a state machine framework using the transitions python3 library.  Adding support for
new devices is fairly easy.  To add support for a new device:

  1. Subclass AVDevice and override the indicated methods to implement the device client communication layer.
     The state machine will drive the calls to these methods when necessary.
  2. Subclass the AVNode class, which inherits PolyInterface.Node.  The AVDevice class defines
     a Listener class that can be inherited by the new class to listen for events from the device client communication
     instances.
  3. Add config parameter parsing to NodeFactory.get_params().
  4. Update NodeFactory.on_ssdp_response() to build the new node.
  5. Update the node definitions, nls entries and editors as needed.
 
The included Pioneer VSX-1021 and Sony Bravia devices are available as examples

### Known Issues
- I'm not sure if remote control pairing is needed on the Sony Bravia.  Prior to writing this node server, I
  created some network resources that used the /sony/IRCC URI to control it.  At that time, I paired my TV to
  get it to work using the SOAP protocol required by that URI.
- Some states of the Bravia TV don't get sent as a notification over the Simple IP Control channel.  Therefore,
  They won't update anything in the ISY.  The NetFlix status is updated as a pseudo input because I use it so
  much, but if NetFlix is selected on the TV remote, ISY will not know that.  Generally, any app that is launched
  does not issue a notification via the Simple IP Control channel.
- The device status doesn't update when the nodeserver stops.  This is because the PolyGlot Interface disconnects
  the MQTT connection prior to calling the nodes stop method which breaks the ability of a node to update any
  ISY related information when it is being stopped.  PolyGlot does know how to modify the controller status and does
  so automatically.  Subclassing the PolyGlot Interface and overriding the stop() method to call the stop
  observers prior to shutting down MQTT would be a solution, but could break things when the PolyGlot interface
  gets updated.
- It's possible, but rare, that a response from a device may get lost if the connection between the nodeserver
  and device gets broken.  The nodeserver attempts to reconnect, but the response to a command that is issued
  just prior to discovering the broken connection is lost.  More intelligent code to cache the command and retry
  it could resolve this.  (Work in progress)
