#!/usr/bin/env python

# import normal packages
import platform
import json
import logging
import sys
import os
import sys
if sys.version_info.major == 2:
    import gobject
else:
    from gi.repository import GLib as gobject
import sys
import time
import requests # for http GET
import configparser # for config/ini file

# our own packages from victron
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))
from vedbus import VeDbusService


class DbusTeslaWallConnectorService:
  def __init__(self, servicename, paths, productname='Tesla WallConnector', connection='Tesla WallConnector HTTP JSON service'):
    config = self._getConfig()
    deviceinstance = int(config['DEFAULT']['Deviceinstance'])
    position = int(config['DEFAULT']['Position'])

    self._dbusservice = VeDbusService("{}.http_{:02d}".format(servicename, deviceinstance))
    self._paths = paths


    ip = (config['DEFAULT']['Host'])
    ip = ip or 'TeslaWallConnector.local'
    url = 'http://' + ip + '/api/1'
    self.VITALS = url + '/vitals'
    self.LIFETIME = url + '/lifetime'
    self.VERSION = url + '/version'

    logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))

    paths_wo_unit = [
      '/Status',  # value 'car' 1: charging station ready, no vehicle 2: vehicle loads 3: Waiting for vehicle 4: Charge finished, vehicle still connected
      '/Mode'
    ]

    #get data from Tesla WallConnector
    version_data = self._getTWCVersionData()

    # Create the management objects, as specified in the ccgx dbus-api document
    self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
    self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
    self._dbusservice.add_path('/Mgmt/Connection', connection)

    # Create the mandatory objects
    self._dbusservice.add_path('/DeviceInstance', deviceinstance)
    self._dbusservice.add_path('/ProductId', 0xFFFF) #
    self._dbusservice.add_path('/ProductName', productname)
    self._dbusservice.add_path('/CustomName', productname)
    if version_data:
       self._dbusservice.add_path('/FirmwareVersion', version_data['firmware_version'])#.replace('.', ',')))
       self._dbusservice.add_path('/Serial', version_data['serial_number'])
       self._dbusservice.add_path('/HardwareVersion', version_data['part_number'])
    self._dbusservice.add_path('/Connected', 1)
    self._dbusservice.add_path('/UpdateIndex', 0)
    self._dbusservice.add_path('/Position', position)

    # add paths without units
    for path in paths_wo_unit:
      self._dbusservice.add_path(path, None)

    # add path values to dbus
    for path, settings in self._paths.items():
      self._dbusservice.add_path(
        path, settings['initial'], gettextcallback=settings['textformat'], writeable=True, onchangecallback=self._handlechangedvalue)

    # add temp handler
    #self._tempservice = self.add_temp_service(100)


    # last update
    self._lastUpdate = 0

    # charging time in float
    self._chargingTime = 0.0

    # add _update function 'timer'
    gobject.timeout_add(2500, self._update) # pause 2.5s before the next request


    # add _signOfLife 'timer' to get feedback in log every 5minutes
    gobject.timeout_add(5*60*1000, self._signOfLife)



  def add_temp_service(self, instance):
    ds = VeDbusService('com.victronenergy.temperature.twc3',bus=dbusconnection())

    # Create the management objects, as specified in the ccgx dbus-api document
    ds.add_path('/Mgmt/ProcessName', __file__)
    ds.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
    ds.add_path('/Mgmt/Connection', 'local')

    # Create the mandatory objects
    ds.add_path('/DeviceInstance', instance)
    ds.add_path('/ProductId', 0)
    ds.add_path('/ProductName', 'dbus-twc3')
    ds.add_path('/FirmwareVersion', 0)
    ds.add_path('/HardwareVersion', 0)
    ds.add_path('/Connected', 1)

    ds.add_path('/CustomName', self._name)
    ds.add_path('/TemperatureType', 2)  # 0=battery, 1=fridge, 2=generic
    ds.add_path('/Temperature', 0)
    ds.add_path('/Status', 0)  # 0=ok, 1=disconnected, 2=short circuit
    return ds

  def _getConfig(self):
    config = configparser.ConfigParser()
    config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
    return config



  def _getGoeChargerMqttPayloadUrl(self, parameter, value):
    config = self._getConfig()

    URL = "http://%s/mqtt?payload=%s=%s" % (config['ONPREMISE']['Host'], parameter, value)

    return URL

  def _setGoeChargerValue(self, parameter, value):
    URL = self._getGoeChargerMqttPayloadUrl(parameter, str(value))
    request_data = requests.get(url = URL)

    # check for response
    if not request_data:
      raise ConnectionError("No response from Tesla WallConnector - %s" % (URL))

    json_data = request_data.json()

    # check for Json
    if not json_data:
        raise ValueError("Converting response to JSON failed")

    if json_data[parameter] == str(value):
      return True
    else:
      logging.warning("Tesla WallConnector parameter %s not set to %s" % (parameter, str(value)))
      return False


  def _getTWCVitalsData(self):
    try:
       request_data = requests.get(url = self.VITALS, timeout=5)
    except Exception:
       return None

    # check for response
    if not request_data:
        raise ConnectionError("No response from Tesla WallConnector - %s" % (URL))

    json_data = request_data.json()

    # check for Json
    if not json_data:
        raise ValueError("Converting response to JSON failed")


    return json_data

  def _getTWCVersionData(self):
    try:
       request_data = requests.get(url = self.VERSION, timeout=5)
    except Exception:
       return None

    # check for response
    if not request_data:
        raise ConnectionError("No response from Tesla WallConnector - %s" % (URL))

    json_data = request_data.json()

    # check for Json
    if not json_data:
        raise ValueError("Converting response to JSON failed")


    return json_data

  def _getTWCLifetimeData(self):
    try:
       request_data = requests.get(url = self.LIFETIME, timeout=5)
    except Exception:
       return None

    # check for response
    if not request_data:
        raise ConnectionError("No response from Tesla WallConnector - %s" % (URL))

    json_data = request_data.json()

    # check for Json
    if not json_data:
        raise ValueError("Converting response to JSON failed")


    return json_data


  def _signOfLife(self):
    logging.info("--- Start: sign of life ---")
    logging.info("Last _update() call: %s" % (self._lastUpdate))
    logging.info("Last '/Ac/Power': %s" % (self._dbusservice['/Ac/Power']))
    logging.info("--- End: sign of life ---")
    return True

  def _update(self):
    try:
       #get data from Tesla WallConnector
       d = self._getTWCVitalsData()
       lt = self._getTWCLifetimeData()

       if d is not None:
          #send data to DBus
          self._dbusservice['/Ac/L1/Power'] = round(float(d['currentA_a']) * float(d['voltageA_v']))
          self._dbusservice['/Ac/L2/Power'] = round(float(d['currentB_a']) * float(d['voltageB_v']))
          self._dbusservice['/Ac/L3/Power'] = round(float(d['currentC_a']) * float(d['voltageC_v']))
          self._dbusservice['/Ac/Power'] = round(self._dbusservice['/Ac/L1/Power'] + self._dbusservice['/Ac/L2/Power'] + self._dbusservice['/Ac/L3/Power'])
          self._dbusservice['/Ac/Frequency'] = round(d['grid_hz'], 1)
          self._dbusservice['/Ac/Voltage'] = round(d['grid_v'])
          self._dbusservice['/Current'] = round(d['vehicle_current_a'], 1)
          self._dbusservice['/SetCurrent'] = 13  # static for now
          self._dbusservice['/MaxCurrent'] = 13  # d['vehicle_current_a']
          # self._dbusservice['/Ac/Energy/Forward'] = float(d['session_energy_wh']) / 1000.0
          self._dbusservice['/Ac/Energy/Forward'] = round(float(lt['energy_wh']) / 1000.0, 3)
          self._dbusservice['/ChargingTime'] = d['session_s']

          state = 0 # disconnected
          if d['vehicle_connected'] == True:
              state = 1 # connected
              if d['vehicle_current_a'] > 1:
                  state = 2 # charging
          self._dbusservice['/Status'] = state
          self._dbusservice['/Mode'] = 0 # Manual, no control
          self._dbusservice['/StartStop'] = 1 # Always on
          self._dbusservice['/MCU/Temperature'] = d['mcu_temp_c']
          self._dbusservice['/PCB/Temperature'] = d['pcba_temp_c']
          self._dbusservice['/Handle/Temperature'] = d['handle_temp_c']

          #self._tempservice['/CustomName'] = self._name + ' Handle'
          #self._tempservice['/Temperature'] = round(d['handle_temp_c'], 1)


          #logging
          logging.debug("Wallbox Consumption (/Ac/Power): %s" % (self._dbusservice['/Ac/Power']))
          logging.debug("Wallbox Forward (/Ac/Energy/Forward): %s" % (self._dbusservice['/Ac/Energy/Forward']))
          logging.debug("---")

          # increment UpdateIndex - to show that new data is available
          index = self._dbusservice['/UpdateIndex'] + 1  # increment index
          if index > 255:   # maximum value of the index
            index = 0       # overflow from 255 to 0
          self._dbusservice['/UpdateIndex'] = index

          #update lastupdate vars
          self._lastUpdate = time.time()
       else:
          logging.debug("Wallbox is not available")

    except Exception as e:
       logging.critical('Error at %s', '_update', exc_info=e)

    # return true, otherwise add_timeout will be removed from GObject - see docs http://library.isr.ist.utl.pt/docs/pygtk2reference/gobject-functions.html#function-gobject--timeout-add
    return True

   def _handlechangedvalue(self, path, value):
     logging.info("someone else updated %s to %s" % (path, value))

     if path == '/SetCurrent':
       return self._setGoeChargerValue('amp', value)
     elif path == '/StartStop':
       return self._setGoeChargerValue('alw', value)
     elif path == '/MaxCurrent':
       return self._setGoeChargerValue('ama', value)
     else:
       logging.info("mapping for evcharger path %s does not exist" % (path))
       return False
         
   def getLogLevel():
     config = self._getConfig()
     logLevelString = config['DEFAULT']['LogLevel']
  
     if logLevelString:
       level = logging.getLevelName(logLevelString)
    else:
       level = logging.INFO
    
     return level
    
def main():
  #configure logging
  config = self._getConfig()
  loglevel = int(config['DEFAULT']['LogLevel'])
  logging.basicConfig(      format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            level=logging.getLogLevel(),
                            handlers=[
                                logging.FileHandler("%s/current.log" % (os.path.dirname(os.path.realpath(__file__)))),
                                logging.StreamHandler()
                            ])

  try:
      logging.info("Start")

      from dbus.mainloop.glib import DBusGMainLoop
      # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
      DBusGMainLoop(set_as_default=True)

      #formatting
      _kwh = lambda p, v: (str(round(v, 2)) + 'kWh')
      _a = lambda p, v: (str(round(v, 1)) + 'A')
      _w = lambda p, v: (str(round(v, 1)) + 'W')
      _v = lambda p, v: (str(round(v, 1)) + 'V')
      _degC = lambda p, v: (str(v) + '°C')
      _s = lambda p, v: (str(v) + 's')

      #start our main-service
      pvac_output = DbusTeslaWallConnectorService(
        servicename='com.victronenergy.evcharger',
        paths={
          '/Ac/Power': {'initial': 0, 'textformat': _w},
          '/Ac/L1/Power': {'initial': 0, 'textformat': _w},
          '/Ac/L2/Power': {'initial': 0, 'textformat': _w},
          '/Ac/L3/Power': {'initial': 0, 'textformat': _w},
          '/Ac/Energy/Forward': {'initial': 0, 'textformat': _kwh},
          '/ChargingTime': {'initial': 0, 'textformat': _s},

          '/Ac/Voltage': {'initial': 0, 'textformat': _v},
          '/Current': {'initial': 0, 'textformat': _a},
          '/SetCurrent': {'initial': 0, 'textformat': _a},
          '/MaxCurrent': {'initial': 0, 'textformat': _a},
          '/MCU/Temperature': {'initial': 0, 'textformat': _degC},
          '/PCB/Temperature': {'initial': 0, 'textformat': _degC},
          '/Handle/Temperature': {'initial': 0, 'textformat': _degC},
          '/StartStop': {'initial': 0, 'textformat': lambda p, v: (str(v))}
          #'/History/ChargingCycles',
          #'/History/ConnectorCycles',
          #'/History/Ac/Energy/Forward',
          #'/History/Uptime',
          #'/History/ChargingTime',
          #'/History/Alerts',
          #'/History/AverageStartupTemperature',
          #'/History/AbortedChargingCycles',
          #'/History/ThermalFoldbacks'
        }
        )

      logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
      mainloop = gobject.MainLoop()
      mainloop.run()
  except Exception as e:
    logging.critical('Error at %s', 'main', exc_info=e)
if __name__ == "__main__":
  main()
