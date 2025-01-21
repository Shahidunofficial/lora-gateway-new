import os

SERIAL_PORT='COM5'
SERIAL_BAUDRATE=115200
MONGODB_URL='mongodb+srv://shahid:g06kC0vHbJ3CslrH@cluster1.esbz2.mongodb.net/stream'

# MQTT Configuration
MQTT_BROKER = 'd549a3b4a5ff42319787adee8807f5e7.s1.eu.hivemq.cloud'
MQTT_PORT = 8883  # TLS port
MQTT_WEBSOCKET_PORT = 8884
MQTT_KEEPALIVE = 60
MQTT_CLIENT_ID = os.getenv('MQTT_CLIENT_ID', f'gateway_{os.getenv("GATEWAY_ID", "G100101")}')
MQTT_QOS = int(os.getenv('MQTT_QOS', 1))
MQTT_RETRY_INTERVAL = int(os.getenv('MQTT_RETRY_INTERVAL', 5))
MQTT_MAX_RETRIES = int(os.getenv('MQTT_MAX_RETRIES', 10))
MQTT_CLEAN_SESSION = os.getenv('MQTT_CLEAN_SESSION', 'true').lower() == 'true'

# TLS/SSL Configuration
MQTT_TLS_ENABLED = True
MQTT_TLS_INSECURE = False

# MQTT Authentication
MQTT_USERNAME = os.getenv('shahidvega')
MQTT_PASSWORD = os.getenv('Shahidvega123')

