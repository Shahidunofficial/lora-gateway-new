from flask import Blueprint, request, jsonify
from controller.gatewayController import GatewayController
from helper.mqtt_manager import MQTTManager

gateway_blueprint = Blueprint('gateway', __name__)
mqtt_manager_instance = MQTTManager()  # Get the singleton instance
gateway_controller = GatewayController(mqtt_manager_instance)

@gateway_blueprint.route('/register', methods=['POST'])
def register_gateway():
    return gateway_controller.register_gateway(request.json)

@gateway_blueprint.route('/unregister', methods=['POST'])
def unregister_gateway():
    return gateway_controller.unregister_gateway()

@gateway_blueprint.route('/status', methods=['GET'])
def check_status():
    return gateway_controller.check_gateway_status() 