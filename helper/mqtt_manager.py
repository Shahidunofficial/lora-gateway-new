import paho.mqtt.client as mqtt
import logging
import json
from datetime import datetime, timezone
import os
from config import MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE, MQTT_CLIENT_ID, MQTT_QOS, MQTT_RETRY_INTERVAL, MQTT_MAX_RETRIES, MQTT_TLS_ENABLED, MQTT_TLS_INSECURE
import time
import threading
import ssl
import certifi

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
            
        # Initialize MQTT client with proper version
        self.client = mqtt.Client(
            client_id=MQTT_CLIENT_ID,
            clean_session=True,
            protocol=mqtt.MQTTv311,
            transport="tcp"
        )
        
        # Configure TLS
        if MQTT_TLS_ENABLED:
            self.client.tls_set()
            self.client.tls_insecure_set(MQTT_TLS_INSECURE)
        
        # Set username and password
        self.client.username_pw_set(
            username=os.getenv('MQTT_USERNAME', 'shahidvega'),
            password=os.getenv('MQTT_PASSWORD', 'Shahidvega123')
        )
        
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish
        self.client.on_disconnect = self._on_disconnect
        self.connected = False
        self.gateway_id = os.getenv('GATEWAY_ID', 'G100101')
        self.controller = None  # Will be set from controller_instance
        self._initialized = True
        self._reconnect_timer = None

    def set_controller(self, controller):
        """Set the controller instance for handling commands"""
        self.controller = controller

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logging.info(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            
            # Subscribe to gateway command topic
            command_topic = f"gateway/{self.gateway_id}/command"
            status_topic = f"gateway/{self.gateway_id}/status"
            self.client.subscribe([(command_topic, 1), (status_topic, 1)])
            logging.info(f"Subscribed to topics: {command_topic}, {status_topic}")
            
            # Publish initial connection status
            self._publish_gateway_status("connected")
        else:
            self.connected = False
            logging.error(f"Failed to connect to MQTT broker with code: {rc}")

    def _on_message(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode())
            topic = message.topic
            
            # Parse gateway ID from topic
            topic_parts = topic.split('/')
            if len(topic_parts) >= 3 and topic_parts[0] == 'gateway':
                gateway_id = topic_parts[1]
                message_type = topic_parts[2]
                
                if message_type == 'command':
                    self._handle_command(gateway_id, payload)
                    
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding message payload: {str(e)}")
        except Exception as e:
            logging.error(f"Error handling message: {str(e)}")

    def _handle_command(self, gateway_id, payload):
        try:
            if not self.controller:
                logging.error("Controller not initialized")
                return
                
            # Pause sensor requests before handling command
            logging.debug("Setting pause_sensor_request flag")
            self.controller.pause_sensor_request.set()
            logging.info("Paused sensor requests for command handling")
            
            action = payload.get('action')
            data = payload.get('data', {})
            correlation_id = payload.get('correlation_id')
            
            response = None
            try:
                if action == 'RELAY_CONTROL':
                    response = self.controller.control_relay(data)
                elif action == 'ENROLL_NODE':
                    response = self.controller.enroll_node(data)
                elif action == 'UNENROLL_NODE':
                    response = self.controller.unenroll_node(data)
                elif action == 'REGISTER_GATEWAY':
                    response = self.controller.register_gateway(data)
                elif action == 'UNREGISTER_GATEWAY':
                    response = self.controller.unregister_gateway()
                else:
                    response = {
                        'success': False,
                        'message': f'Unknown action: {action}'
                    }
            finally:
                # Resume sensor requests after command handling
                logging.debug("Clearing pause_sensor_request flag")
                self.controller.pause_sensor_request.clear()
                logging.info("Resumed sensor requests after command handling")
            
            # Publish response
            self._publish_response(gateway_id, action, response, correlation_id)
            
        except Exception as e:
            logging.error(f"Error handling command: {str(e)}")
            # Ensure sensor requests are resumed even if an error occurs
            if self.controller:
                self.controller.pause_sensor_request.clear()
                logging.info("Resumed sensor requests after error")
            self._publish_response(gateway_id, action, {
                'success': False,
                'message': str(e)
            }, correlation_id)

    def _publish_response(self, gateway_id, action, response, correlation_id):
        try:
            response_topic = f"gateway/{gateway_id}/response"
            payload = {
                'action': action,
                'correlation_id': correlation_id,
                'response': response
            }
            
            self.client.publish(
                response_topic,
                json.dumps(payload),
                qos=1
            )
            logging.info(f"Published response for action {action} to {response_topic}")
            
        except Exception as e:
            logging.error(f"Error publishing response: {str(e)}")

    def _publish_gateway_status(self, status):
        try:
            status_topic = f"gateway/{self.gateway_id}/status"
            payload = {
                'status': status,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'gateway_id': self.gateway_id
            }
            
            self.client.publish(
                status_topic,
                json.dumps(payload),
                qos=1,
                retain=True
            )
        except Exception as e:
            logging.error(f"Error publishing gateway status: {str(e)}")

    def _on_publish(self, client, userdata, mid):
        """Callback when a message is published"""
        logging.debug(f"Message {mid} published successfully")

    def connect(self):
        """Establish connection with the MQTT broker"""
        try:
            if self.connected:
                return True
            
            logging.info(f"Attempting MQTT connection to {MQTT_BROKER}:{MQTT_PORT}")
            
            # Set up will message for unexpected disconnections
            will_topic = f"gateway/{self.gateway_id}/status"
            will_payload = json.dumps({
                'status': 'disconnected',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'gateway_id': self.gateway_id
            })
            
            self.client.will_set(will_topic, will_payload, qos=1, retain=True)
            self.client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
            self.client.loop_start()
            
            # Wait for connection with timeout
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < 10:
                time.sleep(0.1)
            
            if self.connected:
                logging.info("Successfully connected to MQTT broker")
                return True
            else:
                logging.error("Failed to connect to MQTT broker within timeout")
                return False
            
        except Exception as e:
            logging.error(f"Failed to connect to MQTT broker: {str(e)}")
            return False

    def publish_sensor_data(self, gateway_id, node_id, sensor_data):
        try:
            if not self.is_connected():
                if not self.connect():  # Try to reconnect
                    logging.error("Cannot publish - MQTT connection failed")
                    return False

            topic = f"sensor_data/{gateway_id}/{node_id}"
            payload = {
                'gateway_id': gateway_id,
                'node_id': node_id,
                'sensor_data': sensor_data,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            # Publish with existing client instead of creating new one
            result = self.client.publish(
                topic,
                json.dumps(payload),
                qos=1,
                retain=True
            )
            
            if result.rc == 0:
                logging.info(f"Published sensor data to {topic}")
                return True
            else:
                logging.error(f"Failed to publish sensor data with result code: {result.rc}")
                return False

        except Exception as e:
            logging.error(f"Error in publish_sensor_data: {str(e)}")
            return False

    def is_connected(self):
        """Check if connected to MQTT broker"""
        return self.connected and self.client.is_connected()

    def get_subscribed_topics(self):
        """Get list of currently subscribed topics"""
        try:
            command_topic = f"gateway/{self.gateway_id}/command"
            if self.is_connected():
                logging.info(f"Currently subscribed to: {command_topic}")
                return [command_topic]
            else:
                logging.warning("Not connected to MQTT broker")
                return []
        except Exception as e:
            logging.error(f"Error getting subscribed topics: {str(e)}")
            return []

    def _on_disconnect(self, client, userdata, rc):
        """Called when the client disconnects from the broker"""
        self.connected = False
        logging.warning(f"Disconnected from MQTT broker with code: {rc}")
        if rc != 0:
            self._schedule_reconnect()

    def _schedule_reconnect(self):
        """Schedule a reconnection attempt"""
        if not self._reconnect_timer:
            logging.info("Scheduling MQTT reconnection attempt")
            self._reconnect_timer = threading.Timer(5.0, self._reconnect)
            self._reconnect_timer.daemon = True
            self._reconnect_timer.start()

    def _reconnect(self):
        """Attempt to reconnect to the MQTT broker"""
        try:
            if not self.connected:
                logging.info("Attempting to reconnect to MQTT broker")
                self.connect()
        except Exception as e:
            logging.error(f"Failed to reconnect to MQTT broker: {str(e)}")
        finally:
            self._reconnect_timer = None