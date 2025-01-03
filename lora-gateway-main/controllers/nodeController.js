const { json } = require('express');
const { getGatewayCollection } = require('../config/db');
const Node = require('../models/Node');
const EnrolledGateway = require('../models/enrolledGateway');
const MQTTService = require('../services/MQTTService');
const mqttService = require('../services/MQTTService');

// Create a reference to store the gateway map
let gatewayMap;

// Function to initialize the gateway map
const initializeNodeController = (map) => {
    gatewayMap = map;
};

const sendCommandToGateway = async (gateway, command) => {
    return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
            reject(new Error('Command timeout'));
        }, 5000);

        // Create a one-time response handler
        const responseHandler = (response) => {
            clearTimeout(timeout);
            resolve(response);
        };

        // Send the command through WebSocket
        if (gateway.socket) {
            gateway.socket.emit('gateway_command', command, responseHandler);
        } else {
            reject(new Error('Gateway socket not connected'));
        }
    });
};

const enrollNode = async (req, res) => {
    try {
        const { nodeName, nodeId, gatewayId } = req.body;
        const userId = req.user.id;

        // Validate required fields
        if (!nodeId || !gatewayId || !nodeName || !userId) {
            return res.status(400).json({
                success: false,
                message: 'nodeId, gatewayId and nodeName are required'
            });
        }

        // Check if node already exists
        const existingNode = await Node.findOne({nodeName ,nodeId, gatewayId, userId });
        if (existingNode) {
            return res.status(400).json({
                success: false,
                message: 'Node is already enrolled'
            });
        }

        try {
            // Send command via MQTT
            const response = await mqttService.sendCommand(gatewayId, {
                action: 'ENROLL_NODE',
                data: {
                    nodeId,
                    state: "00"
                }
            });

            if (response.success) {
                // Create new node in database
                const newNode = await Node.create({
                    nodeName,
                    nodeId,
                    gatewayId,
                    userId,
                    status: 'active',
                    relay1State: '0',
                    relay2State: '0'
                });

                return res.status(201).json({
                    success: true,
                    message: 'Node enrolled successfully',
                    node: newNode
                });
            }

            return res.status(400).json({
                success: false,
                message: response.message || 'Failed to enroll node'
            });

        } catch (error) {
            if (error.message === 'Command timeout') {
                return res.status(504).json({
                    success: false,
                    message: 'Gateway request timed out'
                });
            }
            throw error;
        }

    } catch (error) {
        console.error('Error enrolling node:', error);
        res.status(500).json({
            success: false,
            message: 'Internal server error',
            error: error.message
        });
    }
};

// Update getGatewayNodes to use the new Node model
const getGatewayNodes = async (req, res) => {
    try {
        const { gatewayId } = req.params;
        const { userId } = req.query; // Get userId from query params
        
        // Find nodes for this gateway and user
        const nodes = await Node.find({ 
            gatewayId,
            userId
        });
        
        res.status(200).json({
            success: true,
            nodes: nodes
        });
    } catch (error) {
        console.error('Error in getGatewayNodes:', error);
        res.status(500).json({
            success: false,
            message: 'Error fetching nodes',
            error: error.message
        });
    }
};

const unenrollNode = async (req, res) => {
    try {
        const { nodeId, gatewayId, userId } = req.body;

        // Check if node exists
        const node = await Node.findOne({ nodeId, gatewayId, userId });
        if (!node) {
            return res.status(404).json({
                success: false,
                message: 'Node not found'
            });
        }

        try {
            // Send command via MQTT
            const response = await mqttService.sendCommand(gatewayId, {
                action: 'UNENROLL_NODE',
                data: {
                    nodeId,
                    state: "70"
                }
            });

            // Modified response check to match actual format
            if (response.success) {
                // Remove node from database
                await Node.deleteOne({ nodeId, gatewayId, userId });

                return res.status(200).json({
                    success: true,
                    message: response.message || 'Node unenrolled successfully'
                });
            }

            return res.status(400).json({
                success: false,
                message: response.message || 'Failed to unenroll node'
            });

        } catch (error) {
            if (error.message === 'Command timeout') {
                return res.status(504).json({
                    success: false,
                    message: 'Gateway request timed out'
                });
            }
            throw error;
        }

    } catch (error) {
        console.error('Error unenrolling node:', error);
        res.status(500).json({
            success: false,
            message: 'Internal server error',
            error: error.message
        });
    }
};

const relayControl = async (req, res) => {
    try {
        const { gatewayId, nodeId, relayNumber, relayState } = req.body;
        const { userId } = req.user;

        // Validate relay state
        if (relayState !== '0' && relayState !== '1') {
            return res.status(400).json({
                success: false,
                message: 'Invalid relay state. Must be "0" or "1"'
            });
        }

        // Send command via MQTT
        try {
            const response = await mqttService.sendCommand(gatewayId, {
                action: 'RELAY_CONTROL',
                data: {
                    nodeId: nodeId,
                    relayNumber: parseInt(relayNumber),
                    relayState: relayState,
                    state: "20"
                }
            });

            if (response.success) {
                // Update database
                const node = await Node.findOneAndUpdate(
                    { nodeId, gatewayId, userId },
                    { [`relay${relayNumber}State`]: relayState },
                    { new: true }
                );

                return res.status(200).json({
                    success: true,
                    message: 'Relay state updated successfully',
                    node
                });
            }

            return res.status(400).json({
                success: false,
                message: response.message || 'Failed to update relay state'
            });

        } catch (error) {
            if (error.message === 'Command timeout') {
                return res.status(504).json({
                    success: false,
                    message: 'Gateway request timed out'
                });
            }
            throw error;
        }

    } catch (error) {
        console.error('Error controlling relay:', error);
        res.status(500).json({
            success: false,
            message: 'Internal server error',
            error: error.message
        });
    }
};

module.exports = {
    enrollNode,
    unenrollNode,
    relayControl,
    getGatewayNodes,
    initializeNodeController
};
