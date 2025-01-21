from flask import jsonify
import logging
from helper.gateway_storage import GatewayStorage
import os

class GatewayController:
    def __init__(self, mqtt_manager):
        self.gateway_storage = GatewayStorage()
        self.mqtt_manager = mqtt_manager
        self.gateway_id = os.getenv('GATEWAY_ID', 'G100101')
        self.status = 'disconnected'
        
        # Set initial status if MQTT is connected
        if self.mqtt_manager.is_connected():
            self.status = 'connected'
            self.mqtt_manager._publish_gateway_status('connected')

    def check_gateway_status(self):
        # Update status based on MQTT connection
        self.status = 'connected' if self.mqtt_manager.is_connected() else 'disconnected'
        
        return {
            'success': True,
            'is_enrolled': self.gateway_storage.is_enrolled(),
            'gateway_id': self.gateway_id,
            'status': self.status,
            'mqtt_connected': self.mqtt_manager.is_connected()
        }

    def register_gateway(self, data):
        try:
            received_gateway_id = data.get('gateway_id')
            correlation_id = data.get('correlation_id')
            
            if not received_gateway_id:
                return self._handle_registration_error('Missing gateway ID', correlation_id)
                
            if received_gateway_id != self.gateway_id:
                return self._handle_registration_error('Gateway ID mismatch', correlation_id)

            # Ensure MQTT connection before registration
            if not self.mqtt_manager.is_connected():
                if not self.mqtt_manager.connect():
                    return self._handle_registration_error('Failed to connect to MQTT broker', correlation_id)

            self.gateway_storage.enroll_gateway(received_gateway_id)
            self.status = 'connected'
            
            # Publish gateway status
            self.mqtt_manager._publish_gateway_status('connected')
            
            response = {
                'success': True,
                'message': 'Gateway registered successfully',
                'gateway_id': received_gateway_id,
                'status': self.status
            }
            
            return response
            
        except Exception as e:
            return self._handle_registration_error(str(e), correlation_id)

    def unregister_gateway(self):
        try:
            self.gateway_storage.unenroll_gateway()
            self.status = 'disconnected'
            
            # Publish disconnected status
            if self.mqtt_manager.is_connected():
                self.mqtt_manager._publish_gateway_status('disconnected')
            
            return {
                'success': True,
                'message': 'Gateway unregistered successfully',
                'status': self.status
            }
            
        except Exception as e:
            logging.error(f"Error unregistering gateway: {str(e)}")
            return {
                'success': False,
                'message': str(e),
                'status': self.status
            }

    def _handle_registration_error(self, message, correlation_id):
        response = {
            'success': False,
            'message': message,
            'status': self.status
        }
        if self.mqtt_manager.is_connected():
            self.mqtt_manager._publish_response(
                self.gateway_id, 
                'REGISTER_GATEWAY', 
                response, 
                correlation_id
            )
        return response


  