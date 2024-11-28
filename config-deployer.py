import yaml
import minimalmodbus
import struct
import datetime
import time
import serial
from serial.rs485 import RS485, RS485Settings
import serial.tools.list_ports
import re
import os
import math
from datetime import datetime, timedelta
from dotenv import load_dotenv

#TAG for troubleshooting --> where the error orginated. 
tag ="[config_deployer.py]"

load_dotenv()

# Port for RS485
PORT_RS485 = '/dev/ttyAMA0'

# Endianess of the register
BYTEORDER_BIG: int = 0  # Big-endian ABCD
BYTEORDER_LITTLE: int = 1  # Little-endian DCBA
BYTEORDER_BIG_SWAP: int = 2 # Mid-Big endian BADC
BYTEORDER_LITTLE_SWAP: int = 3 # Mid-Little endian CDAB

# Fn to Set the respective parity values from the master_gateway.yml file 
def get_parity(parity):
    if parity in ['E', 'e']:
        return serial.PARITY_EVEN
    elif parity in ['O', 'o']:
        return serial.PARITY_ODD
    elif parity in ['N', 'n']:
        return serial.PARITY_NONE
    else:
        raise ValueError(f"{tag} : Invalid parity value: {parity} from .yml file")

# Fn to Handle the Modbus exception error codes 
def handle_modbus_errorcodes(data_reader, e, address):
    if isinstance(e, minimalmodbus.NoResponseError):
        data_reader.instrument._print_debug(f"{tag} : No response from slave at address {address}, Reason : {e}.")
    elif isinstance(e, minimalmodbus.IllegalRequestError):
        data_reader.instrument._print_debug(f"{tag} : Illegal request for address {address}, Reason : {e}.")
    elif isinstance(e, minimalmodbus.SlaveDeviceBusyError):
        data_reader.instrument._print_debug(f"{tag} : Slave device busy on address {address}, Reason : {e}.")
    elif isinstance(e, minimalmodbus.MasterReportedException):
        data_reader.instrument._print_debug(f"{tag} : Master reported issue on address {address}, Reason : {e}.")
    else:
        data_reader.instrument._print_debug(f"{tag} : Communication error: {e}")

# Class for Initialising the Modbus communication
class ModbusReader:
    def connect(self,port,baudrate,parity_connect,stopbits,slave_address,timeout=0.5):
        self.slave_address = slave_address
        self.port = PORT_RS485
        self.instrument = minimalmodbus.Instrument(self.port, self.slave_address)
        self.instrument.serial.baudrate = baudrate
        self.instrument.serial.parity = parity_connect
        self.instrument.serial.stopbits = stopbits
        self.instrument.serial.timeout = timeout
        self.instrument.clear_buffers_before_each_transaction = True
        self.instrument.serial.rs485_mode = RS485Settings(
            rts_level_for_tx=True,   # Set RTS high when transmitting
            rts_level_for_rx=False,  # Set RTS low when receiving
            loopback=False,
            delay_before_tx=0,       # You can adjust according to requirement
            delay_before_rx=0     # You can adjust according to requirement
        )

# Load the YAML configuration file
parameter=""
json_list=[]

# Main function 
if __name__=="__main__":
    print(f"{tag} : Started Writing Data MODBUS RTU - {datetime.now()}")
    data_reader = ModbusReader()

    with open('config_patcher.yml', 'r') as file:
        config = yaml.safe_load(file)

        # Add interval to the current time
#        start_time = datetime.now()
#        nxt_reading_time = start_time + timedelta(seconds=reading_intervl)   
        for slave_config in config['slaves']:
            # Communication settings for the current slave from .yml file 
            communication_settings = slave_config['communication']
            port = communication_settings['port']
            baudrate = communication_settings['baudrate']
            parity = communication_settings['parity']
            stopbits = communication_settings['stopbits']
            parity_connect = get_parity(parity)
           
            print(f"{tag} : Slave Configuration - Port: {port}, Baudrate: {baudrate}, Parity: {parity_connect}, Stop Bits: {stopbits}")
            
            # Slave settings for the current slave from .yml file 
            sensors = slave_config['sensors']
            for sensor in sensors:
                slave_address=sensor['slave_address']
                sensor_id = sensor['id']
                registers = sensor['registers']
                print(f"{tag} : Sensor ID: {sensor_id}")
                
                data_reader.connect(port, baudrate, parity_connect, stopbits,slave_address)
                data_reader.instrument.debug = True
                
                for register in registers:
                    print()
                    print("###########################-CONFIG COUNT-###########################")
                    address = register['address']
                    value = register['value']
                    bytes_to_read = register['bytes']
                    data_type=register['data_type']
                    endian=register['endian']
                    f_code=register['function_code']
                    
                # State Machine by INPUT - datatype
                    # Datatype = 1 : unsigned int 16 bit
                    try:
                        if data_type==1: 
                            print(f"{tag} : Data type is one bit")                       
                            data_reader.instrument.write_bit(registeraddress=address,    # Fn code for writing is 5
                                                                    value=value,
                                                                    functioncode=f_code,
                                                                    )
                    # Datatype = 2 : signed int 16 bit
                        elif data_type==2:  
                            print(f"{tag} : Data type is multiple bits")
                            data_reader.instrument.write_bits(registeraddress=address,   #Fn code for writing bits is 15
                                                                    value=value,
                                                                    )
                            
                    # Datatype = 3 : Write 16-bit        
                        elif data_type==3:  
                            print(f"{tag} : Data type is 16 bit Register")
                            data_reader.instrument.write_register(registeraddress=address,    #Fn code for writing float is 16
                                                               value=value,
                                                               number_of_decimals=0,
                                                               functioncode= f_code,
                                                               signed= False
                                                               )
                    
                    # Datatype = 4 : Long int 32-bit
                        elif data_type==4:
                            print(f"{tag} : Data type is long")                               #Fn code for writing long is 16
                            data_reader.instrument.write_long(registeraddress=address,
                                                              value=value,
                                                              signed= False,
                                                              number_of_registers=bytes_to_read,
                                                              byteorder= endian,
                                                              )
                    # Datatype = 5 : Generic write        
                        elif data_type==5:  
                            print(f"{tag} : Data type is generic")
                            data_reader.instrument._generic_command(functioncode = f_code,
                                                              registeraddress=address,
                                                              value=value,
                                                              number_of_registers=bytes_to_read,
                                                              byteorder= endian,
                                                              payloadformat=_Payloadformat.REGISTER,
                                                             )

                    except Exception as e:
                        handle_modbus_errorcodes(data_reader, e, address)

                    time.sleep(0.1)
                    
