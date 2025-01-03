const { getGatewayCollection } = require('../config/db');
const mongoose = require('mongoose');
const fetch = require('node-fetch');
const EnrolledGateway = require('../models/enrolledGateway');
const User = require('../models/User');
const mqttService = require('../services/MQTTService');
// Create a singleton instance of the Map
let gatewayMap = new Map();

// Function to initialize the gateway map
const initializeGatewayMap = (map) => {
    gatewayMap = map;
};

// Get available gateways
const getAvailableGateways = async (req, res) => {
    try {
        const { userId } = req.params;
        
        // Get all enrolled gateways for this user from the database
        const enrolledGateways = await EnrolledGateway.find({ userId });
        
        // Map over enrolled gateways and add their connection status
        const gatewaysWithStatus = enrolledGateways.map(gateway => {
            const connectedGateway = gatewayMap.get(gateway.gatewayId);
            return {
                gatewayId: gateway.gatewayId,
                status: connectedGateway ? 'online' : 'offline',
                ipAddress: connectedGateway?.ipAddress,
                port: connectedGateway?.port,
                lastUpdated: gateway.updatedAt
            };
        });

        res.json({
            success: true,
            gateways: gatewaysWithStatus
        });
    } catch (error) {
        console.error('Error getting gateway status:', error);
        res.status(500).json({
            success: false,
            message: 'Error getting gateway status'
        });
    }
};

// Enroll a gateway
const enrollGateway = async (req, res) => {
    try {
        const { gatewayId, userId, gatewayName } = req.body;

        // Validate required fields
        if (!gatewayId || !userId || !gatewayName) {
            return res.status(400).json({
                success: false,
                message: 'gatewayId, userId and gatewayName are required'
            });
        }

        // Check if gateway already exists
        const existingGateway = await EnrolledGateway.findOne({ gatewayId, userId });
        if (existingGateway) {
            return res.status(400).json({
                success: false,
                message: 'Gateway is already enrolled'
            });
        }

        try {
            // Send command via MQTT
            const response = await mqttService.sendCommand(gatewayId, {
                action: 'REGISTER_GATEWAY',
                data: {
                    gateway_id: gatewayId,
                    user_id: userId,
                    gateway_name: gatewayName
                }
            });

            if (response.success) {
                const liveGateway = gatewayMap.get(gatewayId);
                
                // Save to MongoDB
                const enrolledGateway = new EnrolledGateway({
                    gatewayId,
                    gatewayName,
                    userId,
                    status: 'enrolled',
                    ipAddress: liveGateway?.ipAddress,
                    port: liveGateway?.port,
                    enrolledAt: new Date(),
                    lastSeen: new Date()
                });

                await enrolledGateway.save();

                // Add gateway to user's gateways array
                const user = await User.findById(userId);
                await user.addGateway({ 
                    gateway_id: gatewayId,
                    status: 'active'
                });

                return res.status(201).json({
                    success: true,
                    message: 'Gateway enrolled successfully',
                    gateway: enrolledGateway
                });
            }

            return res.status(400).json({
                success: false,
                message: response.message || 'Failed to enroll gateway'
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
        console.error('Error enrolling gateway:', error);
        res.status(500).json({
            success: false,
            message: 'Internal server error',
            error: error.message
        });
    }
};

// Get nodes for a specific gateway
const getGatewayNodes = async (req, res) => {
    try {
        const { gatewayId } = req.params;
        
        const collection = mongoose.connection.collection(`nodes`);
        const nodes = await collection.find({}).toArray();
        
        const formattedNodes = nodes.map(node => ({
            nodeId: node.nodeId,
            gatewayId: node.gateway_id,
            relay1State: node.relay1_state || "0",
            relay2State: node.relay2_state || "0",
            timestamp: node.timestamp,
            sensors: {
                temperature: node.sensor_temperature,
                humidity: node.sensor_humidity,
                moisture: node.sensor_moisture
            },
            lastUpdated: node.last_updated
        }));

        res.status(200).json({
            success: true,
            nodes: formattedNodes
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

// Add this to your existing gateway controller
const getEnrolledGateways = async (req, res) => {
    try {
        const { userId } = req.params;
        
        // Get enrolled gateways from database
        const enrolledGateways = await EnrolledGateway.find({ userId });

        // Check online status from gatewayMap
        const gatewaysWithStatus = enrolledGateways.map(gateway => {
            const liveGateway = gatewayMap.get(gateway.gatewayId);
            return {
                gatewayId: gateway.gatewayId,
                status: liveGateway ? liveGateway.status : 'offline',
                enrolledAt: gateway.enrolledAt,
                ipAddress: gateway.ipAddress,
                port: gateway.port
            };
        });

        res.status(200).json({
            success: true,
            gateways: gatewaysWithStatus
        });
    } catch (error) {
        console.error('Error getting enrolled gateways:', error);
        res.status(500).json({
            success: false,
            message: 'Error fetching enrolled gateways',
            error: error.message
        });
    }
};

const unenrollGateway = async (req, res) => {
    try {
        const { gatewayId } = req.body;
        const { userId } = req.user;

        // Check if gateway exists
        const gateway = await EnrolledGateway.findOne({ gatewayId, userId });
        if (!gateway) {
            return res.status(404).json({
                success: false,
                message: 'Gateway not found'
            });
        }

        try {
            // Send command via MQTT
            const response = await mqttService.sendCommand(gatewayId, {
                action: 'UNREGISTER_GATEWAY',
                data: {
                    gateway_id: gatewayId,
                    user_id: userId
                }
            });

            if (response.success) {
                // Remove gateway from database
                await EnrolledGateway.deleteOne({ gatewayId, userId });

                // Remove gateway from user's gateways array
                const user = await User.findById(userId);
                await user.removeGateway(gatewayId);

                return res.status(200).json({
                    success: true,
                    message: 'Gateway unenrolled successfully'
                });
            }

            return res.status(400).json({
                success: false,
                message: response.message || 'Failed to unenroll gateway'
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
        console.error('Error unenrolling gateway:', error);
        res.status(500).json({
            success: false,
            message: 'Internal server error',
            error: error.message
        });
    }
};

module.exports = {
    initializeGatewayMap,
    getAvailableGateways,
    enrollGateway,
    getGatewayNodes,
    getEnrolledGateways,
    unenrollGateway
};
