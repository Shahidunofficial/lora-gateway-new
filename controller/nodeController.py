import serial.tools.list_ports
from serial import Serial, SerialException
from flask import jsonify
from model.nodeModel import NodeModel
import os
import logging
import time
import threading
import datetime
from serial import SerialException
import binascii
import json
from datetime import datetime, timezone
from threading import Lock, Event

class NodeController:
    def __init__(self, mqtt_manager):
        from config import SERIAL_PORT, SERIAL_BAUDRATE
        self.SERIAL_PORT = SERIAL_PORT
        self.SERIAL_BAUDRATE = int(os.getenv('SERIAL_BAUDRATE', '115200'))
        self.GATEWAY_ID = os.getenv('GATEWAY_ID', 'G100101')
        self.node_model = NodeModel(gateway_id=self.GATEWAY_ID)
        self.serial_lock = threading.Lock()
        self.pause_sensor_request = threading.Event()
        self.pause_sensor_request.clear()  # Explicitly set initial state to False
        self.mqtt_manager = mqtt_manager
        
        # Ensure MQTT connection
        if not self.mqtt_manager.is_connected():
            self.mqtt_manager.connect()
            time.sleep(1)  # Give it a moment to establish connection

    def decode_hex_response(self, hex_data):
        try:
            hex_data = hex_data.strip()
            if len(hex_data) % 2 != 0:
                logging.error(f"invalid hex data length: {len(hex_data)}")
                return None

            ascii_response = bytes.fromhex(hex_data).decode('ascii', errors='replace')
            logging.debug(f"Raw hex data: {hex_data}")
            logging.debug(f"Decoded ascii response: {ascii_response}")
            
            # The format is: NODE_ID(7) + GATEWAY_ID(7) + STATE(2) + sensor1,sensor2
            # Extract just the sensor data portion (after the first 16 characters)
            sensor_portion = ascii_response[16:]  # Skip NODE_ID(7) + GATEWAY_ID(7) + STATE(2)
            logging.debug(f"Sensor values portion: {sensor_portion}")
            
            # Split and validate sensor values
            try:
                sensor_values = sensor_portion.split(',')
                if len(sensor_values) == 2:
                    sensor1 = float(sensor_values[0])
                    sensor2 = float(sensor_values[1])
                    logging.debug(f"Parsed raw ADC values - Sensor1: {sensor1}, Sensor2: {sensor2}")
            except ValueError as e:
                logging.error(f"Error parsing sensor values: {str(e)}")
            
            return ascii_response
        except ValueError as e:
            logging.error(f"error decoding hex data:{str(e)}")
            return None

    def encode_message(self, message):
        try:
            hex_message=message.encode('ascii', errors='replace').hex()
            logging.debug(f"original msg: {message}")
            logging.debug(f"encoded hex message{hex_message}")
            return hex_message
        except Exception as e:
              logging.error(f"error encoding mesg {str(e)}")
              return None

    def enroll_node(self, data):
        self.pause_sensor_request.set()
        node_id = data.get('nodeId')
        state = data.get('state')
        correlation_id = data.get('correlation_id')
        ser = None
        lock_acquired = False

        try:
            # Give time for sensor monitoring to notice the pause
            time.sleep(0.5)
            
            if not node_id or not state:
                return {
                    'success': False,
                    'message': 'Missing required fields'
                }

            if self.node_model.node_exists(node_id):
                return {
                    'success': False,
                    'message': 'Node already exists'
                }

            # Try to acquire the lock with timeout
            if not self.serial_lock.acquire(timeout=10):
                return {
                    'success': False,
                    'message': 'Serial port is busy, please try again later'
                }
            
            lock_acquired = True

            # Try opening the port multiple times
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    ser = Serial(self.SERIAL_PORT, self.SERIAL_BAUDRATE, timeout=10)
                    logging.info(f"Successfully opened serial port {self.SERIAL_PORT} on attempt {attempt + 1}")
                    break
                except SerialException as e:
                    if attempt < max_attempts - 1:
                        logging.warning(f"Failed to open port on attempt {attempt + 1}, retrying...")
                        time.sleep(1)
                    else:
                        raise e

            # Clear buffers
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            
            # Format data for P2P transmission
            message = f"{node_id}{self.GATEWAY_ID}{state}"
            hex_message = self.encode_message(message)
            
            if not hex_message:
                return {
                    'success': False,
                    'message': 'Failed to encode message'
                }

            # Format AT command
            at_command = f"AT+PSEND={hex_message}\r\n"
            logging.debug(f"Sending command: {at_command}")
            
            # Send the AT command
            ser.write(at_command.encode('ascii'))
            ser.flush()
            
            # Wait for response
            start_time = time.time()
            while (time.time() - start_time) < 15:
                if ser.in_waiting:
                    response = ser.readline().decode('ascii').strip()
                    logging.debug(f"Received raw response: {response}")
                    
                    if "EVT:RXP2P" in response:
                        parts = response.split(':')
                        if len(parts) >= 5:
                            hex_data = parts[4].strip()
                            ascii_response = self.decode_hex_response(hex_data)
                            
                            if ascii_response:
                                received_node_id = ascii_response[:7]
                                received_status = ascii_response[14:]
                                
                                if received_node_id == node_id and received_status == "90":
                                    result = self.node_model.save_node(node_id, self.GATEWAY_ID)
                                    response_data = {
                                        'success': True,
                                        'message': 'Node enrolled successfully',
                                        'data': result
                                    }
                                    return response_data
                                elif received_status == "80":
                                    return {
                                        'success': False,
                                        'message': 'Node enrollment rejected by device'
                                    }
                
                time.sleep(0.1)
            
            return {
                'success': False,
                'message': 'Timeout waiting for node response'
            }

        except SerialException as e:
            logging.error(f"Serial port error: {str(e)}")
            return {
                'success': False,
                'message': f'Serial port error: {str(e)}'
            }
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return {
                'success': False,
                'message': f'Error enrolling node: {str(e)}'
            }
        finally:
            if ser:
                try:
                    ser.close()
                except Exception as e:
                    logging.error(f"Error closing serial port: {str(e)}")
            if lock_acquired:
                try:
                    self.serial_lock.release()
                except Exception as e:
                    logging.error(f"Error releasing lock: {str(e)}")
            self.pause_sensor_request.clear()
    def control_relay(self, data):
        self.pause_sensor_request.set()
        ser = None
        lock_acquired = False
        
        try:
            # Give time for sensor monitoring to notice the pause
            time.sleep(0.5)
            
            node_id = data.get('nodeId')
            relay_number = data.get('relayNumber')
            relay_state = data.get('relayState')
            state = data.get('state', '20')
            
            # Validate inputs
            if str(relay_number) not in ['1', '2']:
                return {
                    'success': False,
                    'message': 'Invalid relay number. Must be 1 or 2'
                }
            
            # Wait for sensor thread to release lock
            wait_start = time.time()
            while self.serial_lock.locked() and (time.time() - wait_start) < 8:
                time.sleep(0.5)
                logging.debug("Waiting for serial lock to be released...")

            if not self.serial_lock.acquire(timeout=10):
                return {
                    'success': False,
                    'message': 'Could not acquire serial port access'
                }
            
            lock_acquired = True
            
            # Rest of the existing control_relay code...
            relay_code = '00' if relay_number == 1 else '01'
            message = f"{node_id}{self.GATEWAY_ID}{state}{relay_code}{relay_state}"
            hex_message = self.encode_message(message)
            
            if not hex_message:
                return {
                    'success': False,
                    'message': 'Failed to encode message'
                }
            
            response = self._send_serial_command(hex_message)
            return response
            
        except Exception as e:
            logging.error(f"Error controlling relay: {str(e)}")
            return {
                'success': False,
                'message': f'Error controlling relay: {str(e)}'
            }
        finally:
            if lock_acquired:
                try:
                    self.serial_lock.release()
                except Exception as e:
                    logging.error(f"Error releasing lock: {str(e)}")
            self.pause_sensor_request.clear()

    def periodic_sensor_data_request(self):
        while True:
            try:
                # Initial pause check
                if self.pause_sensor_request.is_set():
                    logging.debug("Sensor requests are paused, waiting...")
                    time.sleep(0.5)
                    continue

                nodes = self.node_model.get_all_nodes()
                if not nodes:
                    logging.info("No nodes found for sensor data request")
                    time.sleep(0.3)  # Wait longer when no nodes found
                    continue

                with self.serial_lock:
                    ser = None
                    try:
                        # Check pause state after acquiring lock
                        if self.pause_sensor_request.is_set():
                            logging.debug("Sensor request paused after lock acquisition")
                            if self.serial_lock.locked():
                                self.serial_lock.release()
                            time.sleep(0.1)
                            continue

                        # Serial port setup code...
                        ser = Serial(self.SERIAL_PORT, self.SERIAL_BAUDRATE, timeout=1)
                        
                        for node in nodes:
                            # Check pause state before each node request
                            if self.pause_sensor_request.is_set():
                                logging.debug("Sensor request paused before node processing")
                                if ser:
                                    ser.close()
                                if self.serial_lock.locked():
                                    self.serial_lock.release()
                                time.sleep(0.1)
                                break

                            node_id = node['node_id']
                            retry_count = 0
                            max_retries = 1
                            
                            while retry_count < max_retries:
                                try:
                                    # Clear buffers
                                    ser.reset_input_buffer()
                                    ser.reset_output_buffer()
                                    
                                    # Rest of the existing node processing code...
                                    message = f"{node_id}{self.GATEWAY_ID}10"
                                    hex_message = self.encode_message(message)
                                    if not hex_message:
                                        logging.error(f"Failed to encode message for node {node_id}")
                                        break
                                        
                                    at_command = f"AT+PSEND={hex_message}\r\n"
                                    ser.write(at_command.encode('ascii'))
                                    ser.flush()
                                    
                                    # Existing response handling code...
                                    start_time = time.time()
                                    response_received = False
                                    
                                    while (time.time() - start_time) < 7:
                                        # Check pause state during response wait
                                        if self.pause_sensor_request.is_set():
                                            logging.debug("Sensor request paused during response wait")
                                            if ser:
                                                ser.close()
                                            if self.serial_lock.locked():
                                                self.serial_lock.release()
                                            break
                                        
                                        if ser.in_waiting:
                                            response = ser.readline().decode('ascii').strip()
                                            if "EVT:RXP2P" in response:
                                                # Existing response processing code...
                                                parts = response.split(':')
                                                if len(parts) >= 5:
                                                    hex_data = parts[4].strip()
                                                    sensor_data = self.decode_hex_response(hex_data)
                                                    if sensor_data and len(sensor_data) >= 14:
                                                        self.process_sensor_data(node_id, sensor_data[14:])
                                                        response_received = True
                                                        break
                                        time.sleep(0.1)
                                    
                                    if response_received or self.pause_sensor_request.is_set():
                                        break
                                        
                                    retry_count += 1
                                    if retry_count < max_retries:
                                        logging.warning(f"Retrying sensor request for node {node_id}")
                                        time.sleep(2)
                                        
                                except Exception as e:
                                    logging.error(f"Error requesting sensor data from node {node_id}: {e}")
                                    retry_count += 1
                                    if retry_count < max_retries:
                                        time.sleep(2)
                        
                            if self.pause_sensor_request.is_set():
                                break
                                
                            time.sleep(0)  # Wait between nodes
                            
                    finally:
                        if ser:
                            try:
                                ser.close()
                                logging.debug("Serial port closed successfully")
                            except Exception as e:
                                logging.error(f"Error closing serial port: {str(e)}")
                            
            except Exception as e:
                logging.error(f"Error in periodic sensor data request: {e}")
                if ser:
                    try:
                        ser.close()
                    except:
                        pass

    def process_sensor_data(self, node_id, sensor_data):
        try:
            logging.debug(f"Processing raw sensor data: {sensor_data}")
            
            # Remove the state code (first 2 characters) from sensor data
            sensor_data = sensor_data[2:]  # Skip the state code
            logging.debug(f"Sensor data after removing state: {sensor_data}")
            
            values = sensor_data.split(',')
            logging.debug(f"Split sensor values: {values}")
            
            if len(values) == 2:
                try:
                    # Keep raw ADC values
                    sensor1 = float(values[0])
                    sensor2 = float(values[1])
                    logging.debug(f"Raw ADC values - Sensor1: {sensor1}, Sensor2: {sensor2}")
                    
                    # Maximum retries for MQTT publishing
                    max_retries = 3
                    retry_delay = 2
                    
                    for attempt in range(max_retries):
                        if not self.mqtt_manager.is_connected():
                            logging.warning(f"MQTT not connected. Attempting to reconnect... (Attempt {attempt + 1}/{max_retries})")
                            if not self.mqtt_manager.connect():
                                if attempt < max_retries - 1:
                                    time.sleep(retry_delay)
                                    continue
                                else:
                                    logging.error("Failed to establish MQTT connection after all retries")
                                    return
                        
                        success = self.mqtt_manager.publish_sensor_data(
                            gateway_id=self.GATEWAY_ID,
                            node_id=node_id,
                            sensor_data=sensor_data  # This will now contain only the sensor values
                        )
                        
                        if success:
                            logging.info(f"Published sensor data for node {node_id}: {sensor_data}")
                            return
                        elif attempt < max_retries - 1:
                            logging.warning(f"Failed to publish sensor data, retrying... (Attempt {attempt + 1}/{max_retries})")
                            time.sleep(retry_delay)
                        else:
                            logging.error("Failed to publish sensor data after all retries")
                except ValueError as e:
                    logging.error(f"Error parsing sensor values: {str(e)}")
                    
        except Exception as e:
            logging.error(f"Error processing sensor data: {str(e)}")

    def unenroll_node(self, data):
        self.pause_sensor_request.set()
        node_id = data.get('nodeId')
        state = data.get('state')
        correlation_id = data.get('correlation_id')
        
        try:
            # Wait briefly for sensor monitoring to notice the pause
            time.sleep(0.5)
            
            # Try to acquire the lock with timeout
            if not self.serial_lock.acquire(timeout=10):
                return jsonify({'message': 'Serial port is busy, please try again later'}), 500
            
            lock_acquired = True  # Mark that we successfully acquired the lock
            
            # Rest of your unenroll logic...
            ser = Serial(self.SERIAL_PORT, self.SERIAL_BAUDRATE, timeout=10)
            
            # Clear buffers
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            
            # Format unenroll command
            message = f"{node_id}{self.GATEWAY_ID}{state}"
            hex_message = self.encode_message(message)
            at_command = f"AT+PSEND={hex_message}\r\n"
            
            # Send command
            ser.write(at_command.encode('ascii'))
            ser.flush()
            
            # Wait for response
            start_time = time.time()
            while (time.time() - start_time) < 15:
                if ser.in_waiting:
                    response = ser.readline().decode('ascii').strip()
                    logging.debug(f"Received response: {response}")
                    
                    if "EVT:RXP2P" in response:
                        parts = response.split(':')
                        if len(parts) >= 5:
                            hex_data = parts[4].strip()
                            ascii_response = self.decode_hex_response(hex_data)
                            if ascii_response:
                                received_node_id = ascii_response[7:14]
                                received_status = ascii_response[14:]
                                
                                if received_node_id == node_id:
                                    if received_status == "97":
                                        self.node_model.delete_node(node_id)
                                        response = {
                                            'success': True,
                                            'message': 'Node unenrolled successfully'
                                        }
                                        if self.mqtt_manager:
                                            self.mqtt_manager._publish_response(
                                                self.GATEWAY_ID,
                                                'UNENROLL_NODE',
                                                response,
                                                correlation_id
                                            )
                                        return response
                                    elif received_status == "87":
                                        return jsonify({'message': 'Node unenrollment rejected by device'}), 400
            
                time.sleep(0.1)
                
            return jsonify({'message': 'Timeout waiting for node response'}), 500
            
        except SerialException as e:
            logging.error(f"Serial port error: {str(e)}")
            return jsonify({'message': f'Serial port error: {str(e)}'}), 500
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return jsonify({'message': f'Error unenrolling node: {str(e)}'}), 500
        finally:
            if ser:
                try:
                    ser.close()
                except Exception as e:
                    logging.error(f"Error closing serial port: {str(e)}")
            
            # Only release the lock if we acquired it
            if lock_acquired:
                try:
                    self.serial_lock.release()
                except Exception as e:
                    logging.error(f"Error releasing lock: {str(e)}")
            
            self.pause_sensor_request.clear()

    def _cleanup_serial_port(self):
        """Helper method to clean up serial port"""
        try:
            # First check if port exists
            if not os.path.exists(self.SERIAL_PORT):
                logging.warning(f"Serial port {self.SERIAL_PORT} does not exist")
                return

            import serial.tools.list_ports
            ports = serial.tools.list_ports.comports()
            for port in ports:
                if port.device == self.SERIAL_PORT:
                    try:
                        temp_ser = Serial(port.device)
                        temp_ser.close()
                        del temp_ser  # Explicitly delete the object
                        time.sleep(0.5)
                    except Exception as e:
                        logging.warning(f"Error during port cleanup: {str(e)}")
                        time.sleep(0.5)
        except Exception as e:
            logging.warning(f"Error cleaning up ports: {str(e)}")

    def _send_serial_command(self, hex_message, timeout=15):
        ser = None
        try:
            ser = Serial(self.SERIAL_PORT, self.SERIAL_BAUDRATE, timeout=timeout)
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            
            at_command = f"AT+PSEND={hex_message}\r\n"
            ser.write(at_command.encode('ascii'))
            ser.flush()
            
            start_time = time.time()
            while (time.time() - start_time) < timeout:
                if ser.in_waiting:
                    response = ser.readline().decode('ascii').strip()
                    
                    if "EVT:RXP2P" in response:
                        parts = response.split(':')
                        if len(parts) >= 5:
                            hex_data = parts[4].strip()
                            ascii_response = self.decode_hex_response(hex_data)
                            
                            if ascii_response:
                                received_status = ascii_response[14:]
                                if received_status == "92":
                                    return {'success': True}
                                elif received_status == "82":
                                    return {'success': False, 'message': 'Command rejected by device'}
                                
                time.sleep(0.1)
                
            return {'success': False, 'message': 'Command timeout'}
            
        finally:
            if ser:
                ser.close()

__all__ = ['NodeController']