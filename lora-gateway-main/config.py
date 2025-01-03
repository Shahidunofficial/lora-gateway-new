import os

SERIAL_PORT='COM5'
SERIAL_BAUDRATE=115200
MONGODB_URL='mongodb+srv://shahid:g06kC0vHbJ3CslrH@cluster1.esbz2.mongodb.net/stream'

# MQTT Configuration
MQTT_BROKER = 'localhost'
MQTT_PORT = 1884
MQTT_KEEPALIVE = 60
MQTT_CLIENT_ID = os.getenv('MQTT_CLIENT_ID', f'gateway_{os.getenv("GATEWAY_ID", "G100101")}')
MQTT_QOS = int(os.getenv('MQTT_QOS', 1))
MQTT_RETRY_INTERVAL = int(os.getenv('MQTT_RETRY_INTERVAL', 5))
MQTT_MAX_RETRIES = int(os.getenv('MQTT_MAX_RETRIES', 10))
MQTT_CLEAN_SESSION = os.getenv('MQTT_CLEAN_SESSION', 'true').lower() == 'true'

