import paho.mqtt.client as mqtt
import logging
import json
from datetime import datetime, timezone
import os
from config import MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE, MQTT_CLIENT_ID
import time

class MQTTManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MQTTManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.client = mqtt.Client(
            client_id=MQTT_CLIENT_ID,
            clean_session=True,
            protocol=mqtt.MQTTv31,
            transport="tcp"
        )
        
        logging.info(f"Initializing MQTT Manager with:")
        logging.info(f"Broker: {MQTT_BROKER}")
        logging.info(f"Port: {MQTT_PORT}")
        logging.info(f"Client ID: {MQTT_CLIENT_ID}")
        
        # Set up will message
        will_payload = {
            "status": "disconnected",
            "gateway_id": os.getenv('GATEWAY_ID', 'unknown'),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.client.will_set(
            f"gateway/{os.getenv('GATEWAY_ID', 'unknown')}/status",
            json.dumps(will_payload),
            qos=1,
            retain=True
        )
        
        # Configure network settings
        self.client.max_inflight_messages_set(20)
        self.client.max_queued_messages_set(0)  # Unlimited
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish
        self.connected = False
        self.max_retries = 3
        self.retry_delay = 2
        self._initialized = True

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logging.info(f"Successfully connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            
            # Publish connection status on successful connect
            status_payload = {
                "status": "connected", 
                "gateway_id": os.getenv('GATEWAY_ID', 'unknown'),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            try:
                result = self.client.publish(
                    f"gateway/{os.getenv('GATEWAY_ID', 'unknown')}/status",
                    json.dumps(status_payload),
                    qos=1,
                    retain=True
                )
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    logging.error(f"Failed to publish connection status: {mqtt.error_string(result.rc)}")
            except Exception as e:
                logging.error(f"Error publishing connection status: {str(e)}")
                
        else:
            self.connected = False
            error_messages = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier", 
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorized"
            }
            error_msg = error_messages.get(rc, f"Connection refused - unknown error ({rc})")
            logging.error(f"Failed to connect to MQTT broker: {error_msg}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        if rc != 0:
            error_msg = f"Disconnection with error code {rc}"
            logging.error(f"MQTT {error_msg}")
            logging.error(f"Client ID: {self.client._client_id}")
            logging.error(f"Broker: {MQTT_BROKER}:{MQTT_PORT}")
            # Try to reconnect
            self._try_reconnect()

    def _try_reconnect(self):
        if not self.connected:
            retry_count = 0
            while retry_count < self.max_retries:
                logging.info(f"Attempting to reconnect (attempt {retry_count + 1}/{self.max_retries})")
                try:
                    self.client.loop_stop()
                    self.client.reconnect()
                    time.sleep(1)  # Wait for connection to establish
                    
                    if self.connected:
                        logging.info("Successfully reconnected to MQTT broker")
                        return True
                        
                except Exception as e:
                    logging.error(f"Reconnection attempt failed: {str(e)}")
                    
                retry_count += 1
                if retry_count < self.max_retries:
                    time.sleep(self.retry_delay)
                    
            return False
        return True

    def _on_publish(self, client, userdata, mid):
        logging.debug(f"Message {mid} published successfully")

    def connect(self):
        try:
            logging.info(f"Attempting to connect to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            logging.info(f"Using client ID: {MQTT_CLIENT_ID}")
            
            # Connect to broker
            self.client.connect(
                host=MQTT_BROKER,
                port=MQTT_PORT,
                keepalive=MQTT_KEEPALIVE
            )
            self.client.loop_start()
            
            # Wait for connection
            retry_count = 0
            while not self.connected and retry_count < self.max_retries:
                logging.info(f"Waiting for connection... Attempt {retry_count + 1}")
                time.sleep(self.retry_delay)
                retry_count += 1
            
            if not self.connected:
                self.client.loop_stop()
                logging.error("Failed to establish MQTT connection")
                logging.error(f"Broker: {MQTT_BROKER}:{MQTT_PORT}")
                logging.error(f"Client ID: {MQTT_CLIENT_ID}")
                return False
                
            return True
            
        except Exception as e:
            logging.error(f"Connection error: {str(e)}")
            logging.error(f"Broker: {MQTT_BROKER}:{MQTT_PORT}")
            logging.error(f"Client ID: {MQTT_CLIENT_ID}")
            return False

    def disconnect(self):
        if self.connected:
            try:
                # Publish disconnected status before disconnecting
                status_payload = {
                    "status": "disconnected",
                    "gateway_id": os.getenv('GATEWAY_ID', 'unknown'),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                self.client.publish(
                    f"gateway/{os.getenv('GATEWAY_ID', 'unknown')}/status",
                    json.dumps(status_payload),
                    qos=1,
                    retain=True
                )
                
                self.client.loop_stop()
                self.client.disconnect()
            except Exception as e:
                logging.error(f"Error during disconnect: {str(e)}")
            finally:
                self.connected = False

    def publish_sensor_data(self, gateway_id, node_id, sensor_data):
        """
        Publish sensor data with gateway and node IDs.
        """
        if not self.connected:
            logging.warning("MQTT not connected, attempting to reconnect...")
            if not self.connect():
                logging.error("Failed to reconnect to MQTT broker")
                return False
        
        try:
            payload = {
                'gateway_id': gateway_id,
                'node_id': node_id,
                'sensor_data': sensor_data,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            topic = f"sensor_data/{gateway_id}/{node_id}"
            
            logging.info(f"Publishing to MQTT - Topic: {topic}")
            logging.debug(f"Payload: {json.dumps(payload, indent=2)}")  # Changed to debug level
            
            result = self.client.publish(
                topic,
                json.dumps(payload),
                qos=1
            )
            
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                error_msg = mqtt.error_string(result.rc)
                logging.error(f"Failed to publish: {error_msg}")
                if not self.connected:
                    self._try_reconnect()
                return False
            
            logging.debug(f"Successfully published sensor data to topic {topic}")  # Changed to debug level
            return True
            
        except Exception as e:
            logging.error(f"Error publishing message: {str(e)}")
            return False