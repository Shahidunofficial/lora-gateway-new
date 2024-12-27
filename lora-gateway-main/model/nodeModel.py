from datetime import datetime
import os
import logging
from helper.local_storage import LocalStorage

class NodeModel:
    def __init__(self, gateway_id=None):
        self.local_storage = LocalStorage()
        self.gateway_id = gateway_id or os.getenv('GATEWAY_ID', 'G100101')

    def get_all_nodes(self):
        """Get all nodes from local storage"""
        try:
            nodes = self.local_storage.get_all_nodes()
            return nodes
        except Exception as e:
            logging.error(f"Error getting nodes: {str(e)}")
            return []

    def node_exists(self, node_id):
        try:
            nodes = self.local_storage.get_all_nodes()
            return any(node['node_id'] == node_id for node in nodes)
        except Exception as e:
            logging.error(f"Error checking node existence: {str(e)}")
            return False

    def save_node(self, node_id, gateway_id):
        try:
            node_dict = {
                'node_id': node_id,
                'gateway_id': gateway_id,
                'relay1_state': '0',
                'relay2_state': '0',
                'timestamp': datetime.utcnow().isoformat()
            }
            self.local_storage.add_node(node_dict)
            logging.info(f"Node saved to local storage: {node_dict}")
            return node_dict
        except Exception as e:
            logging.error(f"Error saving node: {str(e)}")
            return None

    def delete_node(self, node_id):
        try:
            self.local_storage.remove_node(node_id)
            return True
        except Exception as e:
            logging.error(f"Error deleting node: {str(e)}")
            return False

    def update_relay_state(self, node_id, relay_key, state):
        """Update relay state in local storage"""
        try:
            nodes = self.local_storage.get_all_nodes()
            for node in nodes:
                if node['node_id'] == node_id:
                    node[relay_key] = state
                    self.local_storage.save_nodes()
                    logging.info(f"Updated {relay_key} to {state} for node {node_id}")
                    return True
            return False
        except Exception as e:
            logging.error(f"Error updating relay state: {str(e)}")
            return False