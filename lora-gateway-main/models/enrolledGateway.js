const mongoose = require('mongoose');

const enrolledGatewaySchema = new mongoose.Schema({
    gatewayName:{
        type: String,
        required: true
    },
    gatewayId: {
        type: String,
        required: true,
        unique: true
    },
    userId: {
        type: String,
        required: true
    },
    status: {
        type: String,
        enum: ['enrolled', 'disconnected'],
        default: 'enrolled'
    },
    enrolledAt: {
        type: Date,
        default: Date.now
    },
    ipAddress: String,
    port: Number
});

module.exports = mongoose.model('EnrolledGateway', enrolledGatewaySchema); 