from flask import Flask
from flask_pymongo import PyMongo
from mongoengine import connect
from pymongo.errors import ServerSelectionTimeoutError
from dotenv import load_dotenv
import os
import time
from router.nodeRoutes import node_blueprint
from router.gatewayRoutes import gateway_blueprint
from flask_cors import CORS
import logging
import socketio
import socket
import sys
import threading
import atexit
from controller.nodeController import NodeController
from config import MONGODB_URL
from helper.gateway_storage import GatewayStorage
from flask_socketio import SocketIO
from mqtt_manager import mqtt_manager_instance

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Initialize Flask app
app = Flask(__name__)
CORS(app)
mongo = PyMongo()

# Initialize Socket.IO client
sio = socketio.Client(logger=True, engineio_logger=True)

# Create a single instance of NodeController
sensor_thread = None



def start_sensor_monitoring():
    gateway_storage = GatewayStorage()
    
    if not gateway_storage.is_enrolled():
        logging.warning("Gateway not enrolled, skipping sensor monitoring")
        return
        
    if not mqtt_manager_instance.connect():
        logging.error("Failed to connect to MQTT broker")
        return
    
    # Get the controller instance from controller_instance instead of creating a new one
    from controller_instance import get_controller
    controller = get_controller()
    retry_count = 0
    max_retries = 3  # Add maximum retry attempts
    
    while True:
        try:
            if controller.pause_sensor_request.is_set():
                logging.debug("Sensor monitoring paused")
                time.sleep(2)
                continue
            
            controller.periodic_sensor_data_request()
            retry_count = 0  # Reset retry count on successful operation
            time.sleep(1)
                
        except PermissionError as e:
            retry_count += 1
            if retry_count >= max_retries:
                logging.error(f"Failed to access serial port after {max_retries} attempts. Please check if COM5 is available and you have proper permissions.")
                time.sleep(30)  # Wait longer before trying again
                retry_count = 0
            else:
                logging.warning(f"Permission error accessing serial port (attempt {retry_count}/{max_retries}): {str(e)}")
                time.sleep(5)  # Wait before retry
        except Exception as e:
            logging.error(f"Error in sensor monitoring loop: {str(e)}")
            time.sleep(2)
def configure_app():
    app.config["MONGO_URI"] = MONGODB_URL
    mongo.init_app(app)
    logging.info("MongoDB configured successfully")
    
    # Initialize controller before registering blueprints
    from controller_instance import init_controller
    init_controller(mqtt_manager_instance)
    
    # Register blueprints
    app.register_blueprint(node_blueprint, url_prefix='/api/nodes')
    app.register_blueprint(gateway_blueprint, url_prefix='/api/gateway')
    logging.info("Route blueprints registered successfully")

def get_local_ip():
    """Get the local IP address of the gateway"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        logging.error(f"Error getting local IP: {e}")
        return "127.0.0.1"

def connect_to_websocket_server():
    """Connect to WebSocket server and register gateway"""
    try:
        # Use WebSocket transport explicitly
        sio.disconnect()  # Ensure clean reconnection
        websocket_url = os.getenv('EXPRESS_SERVER_URL', 'ws://localhost:1886')  # Updated port to match server
        sio.connect(
            websocket_url,
            transports=['websocket'],
            wait_timeout=10
        )
        
        # Prepare gateway registration data to match server expectations
        gateway_data = {
            "gatewayId": os.getenv('GATEWAY_ID', 'G100101'),
            "ipAddress": get_local_ip(),
            "port": int(os.getenv('PORT', 8080))
        }
        
        # Emit registration event
        sio.emit('register_device', gateway_data)
        logging.info(f"Gateway registered with WebSocket server: {gateway_data}")
        
    except Exception as e:
        logging.error(f"Error connecting to WebSocket server: {e}")

@sio.event
def connect():
    logging.info("Connected to WebSocket server")

@sio.event
def disconnect():
    logging.info("Disconnected from WebSocket server")
    # Implement exponential backoff for reconnection
    retry_delay = 5
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            logging.info(f"Attempting to reconnect... (Attempt {retry_count + 1}/{max_retries})")
            connect_to_websocket_server()
            break
        except Exception as e:
            logging.error(f"Reconnection failed: {e}")
            retry_count += 1
            time.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff

def main():
    load_dotenv()
    configure_app()
    
    # Register cleanup function
    connect_to_websocket_server()
    # Start sensor monitoring in a separate thread if gateway is enrolled
    gateway_storage = GatewayStorage()
    if gateway_storage.is_enrolled():
        
        sensor_thread = threading.Thread(target=start_sensor_monitoring, daemon=True)
        sensor_thread.start()
        logging.info("Sensor monitoring thread started")
    
    # Start the Flask app
    port = int(os.getenv('PORT', 8080))
    host = os.getenv('HOST', '0.0.0.0')
    debug = os.getenv('DEBUG', 'True').lower() == 'true'
    
    try:
        app.run(host=host, port=port, debug=debug, use_reloader=False)
    except Exception as e:
        logging.error(f"Error running Flask app: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()