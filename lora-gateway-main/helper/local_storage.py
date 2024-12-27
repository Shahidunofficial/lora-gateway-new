import json
import os
import logging
from typing import List, Dict

class LocalStorage:
    def __init__(self, filename: str = 'node-list.json'):
        self.filename = filename
        self.nodes: List[Dict] = []
        self.load_nodes()

    def load_nodes(self) -> None:
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    self.nodes = json.load(f)
        except json.JSONDecodeError:
            logging.error("JSON decode error: Initializing with an empty list")
            self.nodes = []
        except Exception as e:
            logging.error(f"Error loading nodes from file: {str(e)}")
            self.nodes = []

    def save_nodes(self) -> None:
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.nodes, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving nodes to file: {str(e)}")

    def add_node(self, node: Dict) -> None:
        if node not in self.nodes:
            self.nodes.append(node)
            logging.debug(f"Node added to local storage: {node}")
            self.save_nodes()

    def remove_node(self, node_id: str) -> None:
        self.nodes = [node for node in self.nodes if node['node_id'] != node_id]
        self.save_nodes()

    def get_all_nodes(self) -> List[Dict]:
        return self.nodes
