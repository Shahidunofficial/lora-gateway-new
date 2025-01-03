from flask import Flask
from flask_cors import CORS
import logging
import os
import socket
from dotenv import load_dotenv
import socketio
from router.nodeRoutes import node_blueprint
from router.gatewayRoutes import gateway_blueprint, mqtt_manager_instance
import threading
from controller_instance import init_controller, get_controller
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize Socket.IO client for connecting to main server
sio = socketio.Client(
    logger=True,
    engineio_logger=True,
    reconnection=True,
    reconnection_attempts=0,  # Infinite retries
    reconnection_delay=1,
    reconnection_delay_max=5,
    randomization_factor=0.5,
    handle_sigint=False
)

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        logging.error(f"Error getting local IP: {e}")
        return "127.0.0.1"

def connect_to_server():
    while True:  # Keep trying to connect
        try:
            websocket_url = os.getenv('WEBSOCKET_SERVER_URL', 'http://192.168.43.231:5000')
            logging.info(f"Attempting to connect to server at {websocket_url}")
            
            @sio.event
            def connect():
                logging.info("Connected to WebSocket server")
                # Register gateway
                gateway_data = {
                    "gatewayId": os.getenv('GATEWAY_ID', 'G100101'),
                    "ipAddress": get_local_ip(),
                    "port": int(os.getenv('PORT', 8080))
                }
                sio.emit('register_device', gateway_data)
                logging.info(f"Emitted register_device with data: {gateway_data}")
            
            @sio.event
            def connect_error(data):
                logging.error(f"Connection failed: {data}")
            
            @sio.event
            def disconnect():
                logging.warning("Disconnected from server")
            
            # Connect with explicit transport and options
            sio.connect(
                websocket_url,
                transports=['websocket', 'polling'],
                wait_timeout=10,
                wait=True,
                socketio_path='socket.io'
            )
            break  # If connection successful, break the loop
            
        except Exception as e:
            logging.error(f"Error connecting to server: {str(e)}")
            time.sleep(5)  # Wait before retrying

def start_sensor_monitoring():
    try:
        logging.info("Initializing sensor monitoring thread...")
        controller = get_controller()
        logging.info("Controller obtained successfully in sensor thread")
        
        while True:
            try:
                if controller.pause_sensor_request.is_set():
                    logging.info("Sensor request is paused, waiting...")
                    time.sleep(1)
                    continue
                    
                nodes = controller.node_model.get_all_nodes()
                if nodes:
                    logging.info(f"Found {len(nodes)} nodes to monitor")
                    controller.periodic_sensor_data_request()
                else:
                    logging.info("No nodes found to monitor")
                    time.sleep(5)
                    
            except Exception as e:
                logging.error(f"Error in sensor monitoring: {e}")
                time.sleep(5)
                
    except Exception as e:
        logging.error(f"Fatal error in sensor monitoring thread: {str(e)}")
        raise

def configure_app():
    try:
        success = True
        
        # Initialize controller
        init_controller(mqtt_manager_instance)
        logging.info("Controller initialized successfully")
        
        # Register blueprints
        app.register_blueprint(node_blueprint, url_prefix='/api/nodes')
        app.register_blueprint(gateway_blueprint, url_prefix='/api/gateway')
        logging.info("Route blueprints registered successfully")
        
        # Start sensor monitoring thread
        try:
            sensor_thread = threading.Thread(target=start_sensor_monitoring, daemon=True)
            sensor_thread.start()
            time.sleep(1)  # Give thread time to start
            if sensor_thread.is_alive():
                logging.info("Sensor monitoring thread started successfully")
            else:
                logging.error("Sensor monitoring thread failed to start")
                success = False
        except Exception as e:
            logging.error(f"Failed to start sensor thread: {str(e)}")
            success = False
        
        return success
    except Exception as e:
        logging.error(f"Error in configure_app: {str(e)}")
        return False

if __name__ == '__main__':
    try:
        load_dotenv()
        if not configure_app():
            logging.warning("Application configured with limited functionality")
        
        # Connect to server for IP registration in a separate thread
        server_thread = threading.Thread(target=connect_to_server, daemon=True)
        server_thread.start()
        logging.info("Server connection thread started")
        
        # Start Flask app
        host = '0.0.0.0'
        port = int(os.getenv('PORT', 8080))
        debug = os.getenv('DEBUG', 'True').lower() == 'true'
        
        logging.info(f"Starting server on {host}:{port}")
        app.run(
            host=host,
            port=port,
            debug=True,
            use_reloader=False
        )
    except Exception as e:
        logging.error(f"Error starting server: {str(e)}")