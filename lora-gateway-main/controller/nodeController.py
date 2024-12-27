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

class NodeController:
    def __init__(self, mqtt_manager):
        from config import SERIAL_PORT, SERIAL_BAUDRATE
        self.SERIAL_PORT = SERIAL_PORT
        self.SERIAL_BAUDRATE = int(os.getenv('SERIAL_BAUDRATE', '115200'))
        self.GATEWAY_ID = os.getenv('GATEWAY_ID', 'G100101')
        self.node_model = NodeModel(gateway_id=self.GATEWAY_ID)
        self.serial_lock = threading.Lock()
        self.pause_sensor_request = threading.Event()
        self.mqtt_manager = mqtt_manager

    def decode_hex_response(self,hex_data):
          
          try:
            #remove any whitespace
            hex_data=hex_data.strip()
            if len(hex_data) % 2!=0:
                    logging.error(f"invalid hex data length: {len(hex_data)}")
                    return None

            #convert byte to hex response
            ascii_response= bytes.fromhex(hex_data).decode('ascii', errors='replace')
            logging.debug(f"decoded ascii response: {ascii_response} ")
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
        ser = None

        try:
            # Give time for sensor monitoring to notice the pause
            time.sleep(0.5)
            
            if not node_id or not state:
                return jsonify({'message': 'Missing required fields'}), 400

            if self.node_model.node_exists(node_id):
                return jsonify({'message': 'Node already exists'}), 400

            # Wait for sensor thread to release lock
            wait_start = time.time()
            while self.serial_lock.locked() and (time.time() - wait_start) < 8:
                time.sleep(0.5)
                logging.debug("Waiting for serial lock to be released...")

            if not self.serial_lock.acquire(timeout=8):
                return jsonify({'message': 'Could not acquire serial port access'}), 500

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

            if ser is None:
                raise SerialException("Failed to open serial port after multiple attempts")

            # Clear buffers
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            
            # Format data for P2P transmission
            message = f"{node_id}{self.GATEWAY_ID}{state}"
            hex_message = self.encode_message(message)
            
            if not hex_message:
                raise ValueError("Failed to encode message")

            # Format AT command
            at_command = f"AT+PSEND={hex_message}\r\n"
            logging.debug(f"Sending command: {at_command}")
            
            # Send the AT command
            ser.write(at_command.encode('ascii'))
            ser.flush()
            logging.debug(f"Command sent successfully")

            # Wait for response
            max_wait = 7
            start_time = time.time()
            
            while (time.time() - start_time) < max_wait:
                if ser.in_waiting:
                    try:
                        response = ser.readline().decode('ascii').strip()
                        logging.debug(f"Received raw response: {response}")
                        
                        # Check if response is in EVT:RXP2P format
                        if "EVT:RXP2P" in response:
                            # Parse the hex data from the response
                            parts = response.split(':')
                            if len(parts) >= 5:
                                hex_data = parts[4].strip()  # Get the hex data and remove any whitespace
                                logging.debug(f"Extracted hex data: {hex_data}")
                                
                                # Convert hex to ASCII
                                try:
                                    # For your specific case: 4E323031303031473130303130313930
                                    # This should decode to: N201001G10010190
                                    ascii_response = self.decode_hex_response(hex_data)
                                    logging.debug(f"Decoded ASCII response: {ascii_response}")
                                    
                                    # Extract node ID and check if it matches
                                    received_node_id = ascii_response[:7]  # N201001modify the 
                                    received_gateway_id = ascii_response[7:14]  # G100101
                                    received_status = ascii_response[14:]  # 90
                                    
                                    logging.debug(f"Parsed values - Node ID: {received_node_id}, Gateway ID: {received_gateway_id}, Status: {received_status}")
                                    
                                    if received_node_id == node_id and received_status == "90":
                                        result = self.node_model.save_node(node_id, self.GATEWAY_ID)
                                        return jsonify({'message': 'Node enrolled successfully', 'data': result}), 200
                                    elif received_status == "80":
                                        return jsonify({'message': 'Node enrollment rejected by device'}), 400
                                
                                except ValueError as e:
                                    logging.error(f"Error decoding hex data: {str(e)}")
                                    continue
                    
                    except Exception as e:
                        logging.error(f"Error parsing response: {str(e)}")
                        continue
                    
                time.sleep(0.1)
            
            return jsonify({'message': 'Timeout waiting for node response'}), 500

        except SerialException as e:
            logging.error(f"Serial port error: {str(e)}")
            return jsonify({'message': f'Serial port error: {str(e)}'}), 500
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return jsonify({'message': f'Error enrolling node: {str(e)}'}), 500
        finally:
            if ser:
                try:
                    ser.close()
                    logging.debug("Serial port closed successfully")
                except Exception as e:
                    logging.error(f"Error closing serial port: {str(e)}")
            if self.serial_lock.locked():
                self.serial_lock.release()
            self.pause_sensor_request.clear()
    def control_relay(self, data):
        self.pause_sensor_request.set()
        if not self.serial_lock:
            return jsonify({'message': 'Serial lock not initialized'}), 500
            
        self.pause_sensor_request.set()
        node_id = data.get('nodeId')
        relay_number = data.get('relayNumber')
        relay_state = data.get('relayState')
        state = data.get('state')
        
        ser = None
        lock_acquired = False
        
        try:
            # Wait briefly for sensor monitoring to notice the pause
            time.sleep(0.5)
            
            # Try to acquire lock with timeout
            if not self.serial_lock.acquire(timeout=6):
                logging.warning("Could not acquire serial lock82432727 - timeout")
                return jsonify({'message': 'Could not acquire serial port access - timeout'}), 500
                
            lock_acquired = True
            logging.debug("Serial lock acquired successfully")
            
            # Open serial port
            ser = Serial(self.SERIAL_PORT, self.SERIAL_BAUDRATE, timeout=10)
            
            # Clear buffers
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            
            # Format relay command
            relay_code = '00' if relay_number == 1 else '01'
            message = f"{node_id}{self.GATEWAY_ID}{state}{relay_code}{relay_state}"
            hex_message = self.encode_message(message)
            
            if not hex_message:
                raise ValueError("Failed to encode message")
            
            # Send command
            at_command = f"AT+PSEND={hex_message}\r\n"
            logging.debug(f"Sending command: {at_command}")
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
                                    if received_status == "92":
                                        self.node_model.update_relay_state(node_id, f'relay{relay_number}_state', relay_state)
                                        return jsonify({
                                            'message': f'Relay {relay_number} state updated successfully',
                                            'nodeId': node_id,
                                            'relayNumber': relay_number,
                                            'state': relay_state
                                        }), 200
                                    elif received_status == "82":
                                        return jsonify({'message': 'Relay control rejected by device'}), 400
            
                time.sleep(0.1)
                
            return jsonify({'message': 'Timeout waiting for relay response'}), 500
                
        except SerialException as e:
            logging.error(f"Serial port error: {str(e)}")
            return jsonify({'message': f'Serial port error: {str(e)}'}), 500
        except Exception as e:
            logging.error(f"Error in control_relay: {str(e)}")
            return jsonify({'message': f'Error controlling relay: {str(e)}'}), 500
            
        finally:
            if ser:
                try:
                    ser.close()
                    logging.debug("Serial port closed")
                except Exception as e:
                    logging.error(f"Error closing serial port: {str(e)}")
                    
            if lock_acquired:
                try:
                    self.serial_lock.release()
                    logging.debug("Serial lock released")
                except Exception as e:
                    logging.error(f"Error releasing lock: {str(e)}")
                    
            self.pause_sensor_request.clear()
            logging.debug("Sensor request pause cleared")
      
    def periodic_sensor_data_request(self):
        while True:
            try:
                if self.pause_sensor_request.is_set():
                    logging.debug("Sensor request paused")
                    if 'ser' in locals():
                        ser.close()     
                    if self.serial_lock.locked():
                        self.serial_lock.release()
                    logging.debug("Sensor request paused, waiting...")
                    time.sleep(0.1)
                    continue

                if not self.serial_lock.acquire(timeout=0.2):
                    logging.debug("Could not acquire serial lock, retrying...")
                    continue

                try:
                    nodes = self.node_model.get_all_nodes()
                except Exception as e:
                    logging.error(f"Error getting nodes: {str(e)}")
                    time.sleep(1)
                    continue

                if not nodes:
                    logging.info("No nodes found in database")
                    time.sleep(5)
                    continue

                for node in nodes:
                    if self.pause_sensor_request.is_set():
                        logging.info("Sensor data request paused")
                        logging.debug("Sensor request paused")
                        if 'ser' in locals():
                             ser.close()     
                        if self.serial_lock.locked():
                             self.serial_lock.release()
                        logging.debug("Sensor request paused, waiting...")
                        time.sleep(0.1)
                        continue

                    node_id = node['node_id']
                    try:
                        ser = Serial(self.SERIAL_PORT, self.SERIAL_BAUDRATE, timeout=7)
                        logging.info(f"Opened serial port: {self.SERIAL_PORT}")

                        # Clear buffers
                        ser.reset_input_buffer()
                        ser.reset_output_buffer()

                        # Format sensor request command
                        message = f"{node_id}{self.GATEWAY_ID}10"
                        hex_message = binascii.hexlify(message.encode('ascii')).decode('ascii')
                        at_command = f"AT+PSEND={hex_message}\r\n"

                        logging.debug(f"Sending sensor request to node {node_id}")
                        logging.debug(f"Command: {at_command}")

                        ser.write(at_command.encode('ascii'))
                        ser.flush()
                        logging.info("Command sent successfully.")

                        start_time = time.time()
                        response_received = False

                        while (time.time() - start_time) < 3:  # 5 second timeout
                            if ser.in_waiting:
                                try:
                                    response = ser.readline().decode('ascii').strip()
                                    logging.debug(f"Received response: {response}")

                                    if "EVT:RXP2P" in response:
                                        parts = response.split(':')
                                        if len(parts) >= 5:
                                            hex_data = parts[4].strip()
                                            try:
                                                binary_data = binascii.unhexlify(hex_data)
                                                sensor_data = binary_data.decode('ascii')

                                                if sensor_data:
                                                    sensor_values = sensor_data[14:]  # Skip node_id and gateway_id
                                                    logging.info(f"Node {node_id} - Sensor Data: {sensor_values}")
                                                    
                                                    # Process and publish sensor data
                                                    self.process_sensor_data(node_id, sensor_values)
                                                    response_received = True
                                                    break

                                            except binascii.Error as e:
                                                logging.error(f"Binascii error decoding sensor data from node {node_id}: {str(e)}")
                                            except UnicodeDecodeError as e:
                                                logging.error(f"Unicode decode error from node {node_id}: {str(e)}")
                                except UnicodeDecodeError as e:
                                    logging.error(f"Error decoding serial response: {str(e)}")
                                    continue

                            time.sleep(0.1)

                        if not response_received:
                            logging.warning(f"No response received from node {node_id}")

                    except SerialException as e:
                        logging.error(f"Serial port error in sensor request: {str(e)}")
                    finally:
                        if 'ser' in locals():
                            ser.close()

                    # Wait before requesting from next node
                    time.sleep(2)

                logging.info("=== Sensor Data Request Completed ===\n")

            except Exception as e:
                logging.error(f"Error in periodic sensor data request: {str(e)}")
                time.sleep(1)
            finally:
                if self.serial_lock.locked():
                    self.serial_lock.release()

    def process_sensor_data(self, node_id, sensor_data):
        try:
            # Convert sensor data to JSON
            data = {
                'node_id': node_id,
                'gateway_id': self.GATEWAY_ID,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'sensor_data': sensor_data
            }
            
            # Publish to MQTT using the correct method
            if self.mqtt_manager:
                success = self.mqtt_manager.publish_sensor_data(
                    gateway_id=self.GATEWAY_ID,
                    node_id=node_id,
                    sensor_data=sensor_data
                )
                if success:
                    logging.info(f"Published sensor data for node {node_id}")
                else:
                    logging.warning(f"Failed to publish sensor data for node {node_id}")
            
        except Exception as e:
            logging.error(f"Error processing sensor data: {str(e)}")

    def unenroll_node(self, data):
        self.pause_sensor_request.set()
        node_id = data.get('nodeId')
        state = data.get('state')
        
        ser = None
        lock_acquired = False  # Track if lock was acquired
        
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
                                        return jsonify({'message': 'Node unenrolled successfully'}), 200
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


__all__ = ['NodeController']