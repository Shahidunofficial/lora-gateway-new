from datetime import datetime
import os
import logging
import json

class NodeModel:
    def __init__(self, gateway_id=None):
        self.gateway_id = gateway_id or os.getenv('GATEWAY_ID', 'G100101')
        self.nodes_file = 'node-list.json'

    def _read_nodes(self):
        """Read nodes from local JSON file"""
        try:
            if os.path.exists(self.nodes_file):
                with open(self.nodes_file, 'r') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logging.error(f"Error reading nodes file: {str(e)}")
            return []

    def _save_nodes(self, nodes):
        """Save nodes to local JSON file"""
        try:
            with open(self.nodes_file, 'w') as f:
                json.dump(nodes, f, indent=2)
            return True
        except Exception as e:
            logging.error(f"Error saving nodes file: {str(e)}")
            return False

    def get_all_nodes(self):
        """Get all nodes from local storage"""
        try:
            logging.info("Attempting to fetch all nodes from local storage")
            nodes = self._read_nodes()
            # Filter nodes for current gateway
            nodes = [node for node in nodes if node.get('gateway_id') == self.gateway_id]
            logging.info(f"Successfully fetched {len(nodes)} nodes from local storage")
            return nodes
        except Exception as e:
            logging.error(f"Error fetching nodes from local storage: {str(e)}")
            return []

    def node_exists(self, node_id):
        try:
            nodes = self._read_nodes()
            return any(node['node_id'] == node_id and node['gateway_id'] == self.gateway_id for node in nodes)
        except Exception as e:
            logging.error(f"Error checking node existence: {str(e)}")
            return False

    def save_node(self, node_id, gateway_id):
        try:
            nodes = self._read_nodes()
            node_dict = {
                'node_id': node_id,
                'gateway_id': gateway_id,
                'relay1_state': '0',
                'relay2_state': '0',
                'timestamp': datetime.utcnow().isoformat()
            }
            # Remove any existing node with same ID
            nodes = [node for node in nodes if not (node['node_id'] == node_id and node['gateway_id'] == gateway_id)]
            nodes.append(node_dict)
            if self._save_nodes(nodes):
                logging.info(f"Node saved to local storage: {node_dict}")
                return node_dict
            return None
        except Exception as e:
            logging.error(f"Error saving node: {str(e)}")
            return None

    def delete_node(self, node_id):
        try:
            nodes = self._read_nodes()
            original_length = len(nodes)
            nodes = [node for node in nodes if not (node['node_id'] == node_id and node['gateway_id'] == self.gateway_id)]
            if len(nodes) < original_length:
                if self._save_nodes(nodes):
                    logging.info(f"Node {node_id} deleted from local storage")
                    return True
            return False
        except Exception as e:
            logging.error(f"Error deleting node: {str(e)}")
            return False

    def update_relay_state(self, node_id, relay_key, state):
        """Update relay state in local storage"""
        try:
            nodes = self._read_nodes()
            updated = False
            for node in nodes:
                if node['node_id'] == node_id and node['gateway_id'] == self.gateway_id:
                    node[relay_key] = state
                    updated = True
                    break
            if updated and self._save_nodes(nodes):
                logging.info(f"Updated {relay_key} to {state} for node {node_id}")
                return True
            return False
        except Exception as e:
            logging.error(f"Error updating relay state: {str(e)}")
            return False