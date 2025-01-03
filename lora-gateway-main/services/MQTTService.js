const EventEmitter = require('events');

class MQTTService extends EventEmitter {
    constructor() {
        super();
        this.responseCallbacks = new Map();
    }

    init(aedesInstance) {
        this.aedes = aedesInstance;
    }

    async sendCommand(gatewayId, command) {
        if (!gatewayId) {
            throw new Error('Gateway ID is required');
        }

        if (!command || typeof command !== 'object') {
            throw new Error('Command must be a valid object');
        }

        const correlationId = Date.now().toString();
        
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                this.responseCallbacks.delete(correlationId);
                reject(new Error('Command timeout'));
            }, 5000);
            
            this.responseCallbacks.set(correlationId, { resolve, reject, timeout });
            
            const topic = `gateway/${gatewayId}/command`;
            const message = {
                correlation_id: correlationId,
                ...command
            };
            
            try {
                this.aedes.publish({
                    topic,
                    payload: JSON.stringify(message),
                    qos: 1
                }, (error) => {
                    if (error) {
                        clearTimeout(timeout);
                        this.responseCallbacks.delete(correlationId);
                        reject(new Error(`Failed to publish message: ${error.message}`));
                    }
                });
            } catch (error) {
                clearTimeout(timeout);
                this.responseCallbacks.delete(correlationId);
                reject(new Error(`Error publishing message: ${error.message}`));
            }
        });
    }

    handleResponse(gatewayId, response) {
        const { correlation_id, success, data, error } = response;
        const callback = this.responseCallbacks.get(correlation_id);
        
        if (callback) {
            clearTimeout(callback.timeout);
            this.responseCallbacks.delete(correlation_id);
            
            if (success) {
                callback.resolve(data);
            } else {
                callback.reject(new Error(error || 'Command failed'));
            }
        }
    }
}

// Export a singleton instance instead of the class
const mqttService = new MQTTService();
module.exports = mqttService; 