import logging
from .zware import zware
from .devices.BasicDevice import BasicDevice
from .devices.DimmerDevice import DimmerDevice
from .devices.BinarySensorDevice import BinarySensorDevice
from .devices.BinaryPowerSwitchDevice import BinaryPowerSwitchDevice
from .devices.MultiSensorDevice import MultiSensorDevice

from xml.etree.ElementTree import tostring

logger = logging.getLogger('CLAIRE.DataLogger.NetworkService')

class NetworkService():
    def __init__(self, zware_address, zware_user, zware_password):
        # Connect to Z-Wave
        r = zware.zw_init(zware_address,zware_user,zware_password)
        v = r.findall("./version")[0]
        logger.info("Connected to zware version: " + v.get('app_major') + '.' + v.get('app_minor'))

    def get_home_id(self):
        rn = zware.zw_api("zw_info")
        zw_info = rn.find("./zw_info")

        return zw_info.get('home_id')

    def initialize_devices(self):
        devices = []

        # Get all devices
        logger.info("Retrieving all nodes from the ZIP Gateway through ZWare")

        # Get all nodes
        rn = zware.zw_api("zwnet_get_node_list")

        nodes = rn.findall("./zwnet/zwnode")
        for node in nodes:
            # print("Getting node " + node.get("desc"))
            # For each node get all endpoints
            endpoints_request = zware.zw_api("zwnode_get_ep_list", "noded=" + node.get('desc'))
            # Most devices will only have one endpoint, but lets iterate through just in case
            endpoints = endpoints_request.findall("./zwnode/zwep")
            for endpoint in endpoints:
                #print(tostring(endpoint))
                logger.info("Found endpoint device with id: " + endpoint.get('desc') + " called " + endpoint.get('name') + " in " + endpoint.get("loc"))
                # Create device
                device = None
                if int(endpoint.get('generic')) == 17: # Dimmer
                    device = DimmerDevice(endpoint.get('desc'), endpoint.get('name'), endpoint.get("loc"), 0)
                elif int(endpoint.get('generic')) == 16: # Binary Power Switch
                    device = BinaryPowerSwitchDevice(endpoint.get('desc'), endpoint.get('name'), endpoint.get("loc"), 0)
                elif int(endpoint.get('generic')) == 32: # Binary Sensor
                    device = BinarySensorDevice(endpoint.get('desc'), endpoint.get('name'), endpoint.get("loc"), 0)
                elif int(endpoint.get('generic')) == 33: # Multi Sensor
                    device = MultiSensorDevice(endpoint.get('desc'), endpoint.get('name'),endpoint.get("loc"), 0)
                else:
                    device = BasicDevice( endpoint.get('desc'), endpoint.get('name'),endpoint.get("loc"), 0 )
                devices.append(device)

        return devices

    def update_device_state(self, device):
        anything_changed = False

        device_status = zware.zw_api("zwep_get_if_list", "epd=" + device.device_id)

        if isinstance(device, DimmerDevice):
            interface = device_status.find(".//zwif[@name='COMMAND_CLASS_SWITCH_MULTILEVEL']")
            r = zware.zwif_level_api(interface.get('desc'), 3)
            state = int(r.get('state'))

            if state != device.state:
                anything_changed = True
                device.state = state
        elif isinstance(device, BinarySensorDevice):
            interface = device_status.find(".//zwif[@name='COMMAND_CLASS_SENSOR_BINARY']")
            if interface != None:
                r = zware.zwif_bsensor_api(interface.get('desc'), 3)
                state = int(r.get('state'))
                if state != device.state:
                    anything_changed = True
                    device.state = state
        elif isinstance(device, BinaryPowerSwitchDevice):
            interface = device_status.find(".//zwif[@name='COMMAND_CLASS_SWITCH_BINARY']")
            if interface != None:
                r = zware.zwif_switch_api(interface.get('desc'), 3)
                state = int(r.get('state'))
                if state != device.state:
                    anything_changed = True
                    device.state = state

            interface = device_status.find(".//zwif[@name='COMMAND_CLASS_METER']")
            if interface != None:
                # Get instantanous power consumption (unit=2)
                r = zware.zwif_meter_api(interface.get('desc'), 3, "&unit=2")
                power_state = float(r.get('value'))
                if power_state != device.power_state:
                    anything_changed = True
                    device.power_state = power_state
        elif isinstance(device, MultiSensorDevice):
            interface = device_status.find(".//zwif[@name='COMMAND_CLASS_BASIC']")
            if interface != None:
                try:
                    r = zware.zwif_basic_api(interface.get('desc'), 2)
                    r = zware.zwif_basic_api(interface.get('desc'), 3)
                    state = int(r.get('state'))
                except:
                    state = device.state
                if state != device.state:
                    anything_changed = True
                    device.state = state

            interface = device_status.find(".//zwif[@name='COMMAND_CLASS_SENSOR_MULTILEVEL']")
            if interface != None:
                try:
                    r = zware.zwif_api('sensor', interface.get('desc'), 2, "&type=1&unit=0")
                    sensor = r.find('.//sensor')
                    temperature = float(sensor.get('value'))

                    r = zware.zwif_api('sensor', interface.get('desc'), 2, "&type=3&unit=1")
                    sensor = r.find('.//sensor')
                    lux = float(sensor.get('value'))

                except:
                    temperature = device.temperature
                    lux = device.lux

                if temperature != device.temperature:
                    anything_changed = True
                    device.temperature = temperature

                if lux != device.lux:
                    anything_changed = True
                    device.lux = lux


        #elif isinstance(device, BasicDevice):
            # Dont do anything the basic command class implementation does not seem to work
            #interface = device_status.find(".//zwif[@name='COMMAND_CLASS_BASIC']")
            #if interface != None:
            #    r = zware.zwif_basic_api(interface.get('desc'), 3)
            #    state = int(r.get('state'))

            #    if state != device.state:
            #        anything_changed = True
            #        device.state = state

        return anything_changed

    def change_device_state(self, device_id, new_state):
        self.send_command(device_id, 'COMMAND_CLASS_BASIC', 'basic', 4, str.format('&value={}', new_state))

    def get_command_classes(self, device_id):
        device_status = zware.zw_api("zwep_get_if_list", "epd=" + device_id)

        return list(map(lambda i: i.get('name'), device_status.findall(".//zwif")))


    def send_command(self, device_id, command_class, command, number, args):
        device_status = zware.zw_api("zwep_get_if_list", "epd=" + device_id)

        interface = device_status.find(".//zwif[@name='" + command_class + "']")
        if interface != None:
            try:
                return zware.zwif_api(command, interface.get('desc'), number, args)
            except:
                print("Error while executing command")
