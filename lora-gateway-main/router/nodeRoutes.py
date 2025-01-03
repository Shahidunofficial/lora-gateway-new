from flask_socketio import emit
import logging
from datetime import datetime
import os
from flask import Blueprint, request, jsonify
from controller_instance import get_controller

node_blueprint = Blueprint('node', __name__)

@node_blueprint.route('/enroll', methods=['POST'])
def enroll_node():
    controller = get_controller()
    return controller.enroll_node(request.json)

@node_blueprint.route('/unenroll', methods=['POST'])
def unenroll_node():
    controller = get_controller()
    return controller.unenroll_node(request.json)

@node_blueprint.route('/control-relay', methods=['POST'])
def control_relay():
    controller = get_controller()
    return controller.control_relay(request.json)

class WebSocketHandler:
    def __init__(self, socketio):
        self.socketio = socketio
        self.setup_event_handlers()
        logging.info("WebSocket handler initialized")

    def setup_event_handlers(self):
        @self.socketio.on('connect')
        def handle_connect():
            logging.info("Client connected to WebSocket")
            emit('connection_status', {
                'success': True,
                'status': 'connected',
                'message': 'Successfully connected to gateway'
            })

        @self.socketio.on('disconnect')
        def handle_disconnect():
            logging.info("Client disconnected from WebSocket")

        @self.socketio.on('ping')
        def handle_ping():
            emit('pong', {
                'success': True,
                'timestamp': datetime.now().isoformat()
            })
