from flask import jsonify
import logging
from helper.gateway_storage import GatewayStorage
import os

class GatewayController:
    def __init__(self):
        self.gateway_storage = GatewayStorage()
        
    def register_gateway(self, data):
        received_gateway_id = data.get('gateway_id')
        if not received_gateway_id:
            return jsonify({'message': 'Missing gateway ID'}), 400

        # Get the program's gateway ID from environment
        program_gateway_id = os.getenv('GATEWAY_ID')
        
        if not program_gateway_id:
            return jsonify({'message': 'Program gateway ID not configured'}), 400
            
        if received_gateway_id != program_gateway_id:
            return jsonify({'message': 'Gateway ID mismatch'}), 403

        try:
            # Save gateway ID to local storage
            self.gateway_storage.enroll_gateway(received_gateway_id)
            
            # Start sensor monitoring after successful enrollment
            from app import start_sensor_monitoring
            import threading
            sensor_thread = threading.Thread(target=start_sensor_monitoring, daemon=True)
            sensor_thread.start()
            logging.info("Sensor monitoring thread started after gateway enrollment")
            
            return jsonify({
                'message': 'Gateway enrolled successfully',
                'gateway_id': received_gateway_id,
                'status': 'enrolled'
            }), 200
        except Exception as e:
            logging.error(f"Error registering gateway: {str(e)}")
            return jsonify({'message': f'Error registering gateway: {str(e)}'}), 500

    def unregister_gateway(self):
        try:
            self.gateway_storage.unenroll_gateway()
            if 'GATEWAY_ID' in os.environ:
                del os.environ['GATEWAY_ID']
            return jsonify({'message': 'Gateway unregistered successfully'}), 200
        except Exception as e:
            logging.error(f"Error unregistering gateway: {str(e)}")
            return jsonify({'message': f'Error unregistering gateway: {str(e)}'}), 500

    def check_gateway_status(self):
        return jsonify({
            'is_enrolled': self.gateway_storage.is_enrolled(),
            'gateway_id': self.gateway_storage.get_gateway_id()
        }), 200


  