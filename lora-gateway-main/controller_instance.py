from controller.nodeController import NodeController

_controller_instance = None

def init_controller(mqtt_manager):
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = NodeController(mqtt_manager)
    return _controller_instance

def get_controller():
    global _controller_instance
    if _controller_instance is None:
        raise RuntimeError("Controller not initialized. Call init_controller first.")
    return _controller_instance 