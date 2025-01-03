from flask import jsonify
import logging
from helper.gateway_storage import GatewayStorage
import os

class GatewayController:
    def __init__(self, mqtt_manager):
        self.gateway_storage = GatewayStorage()
        self.mqtt_manager = mqtt_manager
        self.gateway_id = os.getenv('GATEWAY_ID', 'G100101')
        
    def register_gateway(self, data):
        received_gateway_id = data.get('gateway_id')
        correlation_id = data.get('correlation_id')
        
        if not received_gateway_id:
            response = {
                'success': False,
                'message': 'Missing gateway ID'
            }
            self.mqtt_manager._publish_response(self.gateway_id, 'REGISTER_GATEWAY', response, correlation_id)
            return response

        program_gateway_id = os.getenv('GATEWAY_ID')
        
        if not program_gateway_id:
            response = {
                'success': False,
                'message': 'Program gateway ID not configured'
            }
            self.mqtt_manager._publish_response(self.gateway_id, 'REGISTER_GATEWAY', response, correlation_id)
            return response
            
        if received_gateway_id != program_gateway_id:
            response = {
                'success': False,
                'message': 'Gateway ID mismatch'
            }
            self.mqtt_manager._publish_response(self.gateway_id, 'REGISTER_GATEWAY', response, correlation_id)
            return response

        try:
            self.gateway_storage.enroll_gateway(received_gateway_id)
            
            from app import start_sensor_monitoring
            import threading
            sensor_thread = threading.Thread(target=start_sensor_monitoring, daemon=True)
            sensor_thread.start()
            
            response = {
                'success': True,
                'message': 'Gateway enrolled successfully',
                'gateway_id': received_gateway_id,
                'status': 'enrolled'
            }
            self.mqtt_manager._publish_response(self.gateway_id, 'REGISTER_GATEWAY', response, correlation_id)
            return response
            
        except Exception as e:
            logging.error(f"Error registering gateway: {str(e)}")
            response = {
                'success': False,
                'message': f'Error registering gateway: {str(e)}'
            }
            self.mqtt_manager._publish_response(self.gateway_id, 'REGISTER_GATEWAY', response, correlation_id)
            return response

    def unregister_gateway(self, data=None):
        correlation_id = data.get('correlation_id') if data else None
        
        try:
            self.gateway_storage.unenroll_gateway()
            if 'GATEWAY_ID' in os.environ:
                del os.environ['GATEWAY_ID']
            
            response = {
                'success': True,
                'message': 'Gateway unregistered successfully'
            }
            self.mqtt_manager._publish_response(self.gateway_id, 'UNREGISTER_GATEWAY', response, correlation_id)
            return response
            
        except Exception as e:
            logging.error(f"Error unregistering gateway: {str(e)}")
            response = {
                'success': False,
                'message': f'Error unregistering gateway: {str(e)}'
            }
            self.mqtt_manager._publish_response(self.gateway_id, 'UNREGISTER_GATEWAY', response, correlation_id)
            return response

    def check_gateway_status(self):
        return {
            'success': True,
            'is_enrolled': self.gateway_storage.is_enrolled(),
            'gateway_id': self.gateway_storage.get_gateway_id()
        }


  