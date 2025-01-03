const mongoose = require('mongoose');

const nodeSchema = new mongoose.Schema({
    nodeId: {
        type: String,
        required: true,
        unique: true
    },
    nodeName: {
        type: String,
        default: function() {
            return `Node-${this.nodeId}`;
        }
    },
    userId: {
        type: String,
        required: true
    },
    gatewayId: {
        type: String,
        required: true
    },
    status: {
        type: String,
        enum: ['active', 'inactive'],
        default: 'active'
    },
    relay1State: {
        type: String,
        enum: ['0', '1'],
        default: '0'
    },
    relay2State: {
        type: String,
        enum: ['0', '1'],
        default: '0'
    },
    sensors: {
        temperature: Number,
        humidity: Number,
        moisture: Number
    },
    enrolledAt: {
        type: Date,
        default: Date.now
    },
    lastUpdated: {
        type: Date,
        default: Date.now
    }
});

module.exports = mongoose.model('Node', nodeSchema); 