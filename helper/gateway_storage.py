import json
import os
import logging
from datetime import datetime

class GatewayStorage:
    def __init__(self, filename: str = 'gateway-status.json'):
        self.filename = filename
        self.gateway_status = self.load_status()

    def load_status(self):
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    return json.load(f)
            return {
                'gateway_id': None,
                'is_enrolled': False,
                'enrolled_at': None
            }
        except Exception as e:
            logging.error(f"Error loading gateway status: {str(e)}")
            return {
                'gateway_id': None,
                'is_enrolled': False,
                'enrolled_at': None
            }

    def save_status(self):
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.gateway_status, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving gateway status: {str(e)}")

    def enroll_gateway(self, gateway_id: str) -> bool:
        self.gateway_status = {
            'gateway_id': gateway_id,
            'is_enrolled': True,
            'enrolled_at': datetime.utcnow().isoformat()
        }
        self.save_status()
        return True

    def unenroll_gateway(self) -> bool:
        self.gateway_status = {
            'gateway_id': None,
            'is_enrolled': False,
            'enrolled_at': None
        }
        self.save_status()
        return True

    def is_enrolled(self) -> bool:
        return self.gateway_status.get('is_enrolled', False)

    def get_gateway_id(self) -> str:
        return self.gateway_status.get('gateway_id') 