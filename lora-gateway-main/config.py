import os

SERIAL_PORT='COM5'
SERIAL_BAUDRATE=115200
MONGODB_URL='mongodb+srv://shahid:g06kC0vHbJ3CslrH@cluster1.esbz2.mongodb.net/stream'

# MQTT Configuration
MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
MQTT_PORT = 1886
MQTT_KEEPALIVE = 60
MQTT_CLIENT_ID = os.getenv('MQTT_CLIENT_ID', f'gateway_{os.getenv("GATEWAY_ID", "G100101")}')

# Ensure client ID is properly formatted
if not MQTT_CLIENT_ID.startswith('gateway_'):
    MQTT_CLIENT_ID = f'gateway_{MQTT_CLIENT_ID}'

MQTT_TOPIC_PREFIX = 'gateway'
