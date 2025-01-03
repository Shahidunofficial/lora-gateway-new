const aedes = require('aedes')({
    protocolVersion: 4,  // MQTT 3.1.1
    protocolId: 'MQTT',
    allowLegacyProtocols: true
});
const net = require('net');
const ws = require('websocket-stream');
const mongoose = require('mongoose');
const mqttService = require('../services/MQTTService');

const startMQTTServer = (port = 1884) => {
    // Create TCP server for MQTT
    mqttService.init(aedes);
    const server = net.createServer(aedes.handle);
    
    // Create WebSocket server for MQTT (use port + 1 for WebSocket)
    const wsServer = require('http').createServer();
    ws.createServer({ server: wsServer }, aedes.handle);

    // Handle client connections
    aedes.on('client', function (client) {
        console.log('Client Connected:', client.id);
    });

    // Subscribe to topics when a client connects
    aedes.on('clientReady', function (client) {
        console.log('Client Ready:', client.id);
        
        // Subscribe to gateway status topic
        client.subscribe({
            topic: 'gateway/G100101/status',
            qos: 0
        }, (err) => {
            if (err) {
                console.error('Error subscribing to status topic:', err);
            } else {
                console.log('Subscribed to gateway status topics');
            }
        });

        // Subscribe to sensor data topic
        client.subscribe({
            topic: 'sensor_data/+/+',
            qos: 0
        }, (err) => {
            if (err) {
                console.error('Error subscribing to sensor data topic:', err);
            } else {
                console.log('Subscribed to sensor data topics');
            }
        });
    });

    // Handle published messages
    aedes.on('publish', function (packet, client) {
        if (client) {
            if (packet.topic.startsWith('gateway/')) {
                console.log('Gateway Status Update:', {
                    topic: packet.topic,
                    payload: packet.payload.toString()
                });
            } else if (packet.topic.startsWith('sensor_data/')) {
                console.log('Sensor Data Received:', {
                    topic: packet.topic,
                    payload: packet.payload.toString()
                });
            }
        }
    });

    // Listen on TCP port
    server.listen(port, '0.0.0.0', function () {
        console.log('MQTT TCP server started and listening on port', port);
    });

    // Listen on WebSocket port (port + 1)
    wsServer.listen(port + 1, '0.0.0.0', function () {
        console.log('MQTT WebSocket server started and listening on port', port + 1);
        console.log('Subscribed topics:');
        console.log('- gateway/+/status');
        console.log('- sensor_data/+/+');
    });

    // Handle published messages
    aedes.on('publish', function (packet, client) {
        if (client) {
            if (packet.topic.match(/gateway\/.*\/response/)) {
                try {
                    const gatewayId = packet.topic.split('/')[1];
                    const payload = JSON.parse(packet.payload.toString());
                    console.log('Received response:', payload); // Add logging
                    
                    // Extract success and message from the nested response
                    const response = {
                        correlation_id: payload.correlation_id,
                        success: payload.response.success,
                        message: payload.response.message,
                        data: payload.response
                    };
                    
                    mqttService.handleResponse(gatewayId, response);
                } catch (error) {
                    console.error('Error processing response:', error);
                }
            }
        }
    });

    return aedes;
};

module.exports = { startMQTTServer }; 