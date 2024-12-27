from flask import Blueprint, request, jsonify
from middleware.gateway_middleware import require_gateway_enrollment
from flask_cors import CORS
from controller_instance import get_controller
import logging

node_blueprint = Blueprint('nodes', __name__)

@node_blueprint.route('/', methods=['GET'])
@require_gateway_enrollment
def get_all_nodes():
    controller = get_controller()
    return controller.get_all_nodes()

@node_blueprint.route('/<node_id>', methods=['GET'])
@require_gateway_enrollment
def get_node(node_id):
    controller = get_controller()
    return controller.get_node(node_id)

@node_blueprint.route('/add', methods=['POST'])
@require_gateway_enrollment
def add_node():
    controller = get_controller()
    print("Request method:", request.method)
    print("Request data:", request.json)
    return controller.enroll_node(request.json)

@node_blueprint.route('/<node_id>', methods=['PUT'])
@require_gateway_enrollment
def update_node(node_id):
    controller = get_controller()
    return controller.update_node(node_id, request.json)

@node_blueprint.route('/<node_id>', methods=['DELETE'])
@require_gateway_enrollment
def delete_node(node_id):
    controller = get_controller()
    return controller.delete_node(node_id)

@node_blueprint.route('/<node_id>/relay/<int:relay_number>', methods=['PUT'])
@require_gateway_enrollment
def update_relay_state(node_id, relay_number):
    controller = get_controller()
    state = request.json.get('state')
    if state is None:
        return jsonify({'error': 'State is required'}), 400
    return controller.update_relay_state(node_id, relay_number, state)

@node_blueprint.route('/<node_id>/relay', methods=['POST'])
@require_gateway_enrollment
def control_relay(node_id):
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
            
        # Add node_id to the request data
        data['nodeId'] = node_id
        controller = get_controller()
        if controller is None:
            return jsonify({'error': 'Controller not initialized'}), 500
            
        return controller.control_relay(data)
    except Exception as e:
        logging.error(f"Error in control_relay: {str(e)}")
        return jsonify({'error': str(e)}), 500

@node_blueprint.route('/unenroll', methods=['POST'])
@require_gateway_enrollment
def unenroll_node():
    controller = get_controller()
    print("Request method:", request.method)
    print("Request data:", request.json)
    return controller.unenroll_node(request.json)
