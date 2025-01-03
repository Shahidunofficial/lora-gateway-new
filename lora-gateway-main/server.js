const express = require("express");
const { Server } = require("socket.io");
const http = require("http");
const cors = require("cors");
const dotenv = require("dotenv");
const colors = require("colors");
const morgan = require("morgan");
const { connectDB } = require("./config/db");
const { initializeGatewayMap } = require('./controllers/gatewayController');
const { initializeNodeController } = require('./controllers/nodeController');
const { startMQTTServer } = require('./mqtt/mqttServer');
const User = require('./models/User');

// DOTENV
dotenv.config();

// MONGODB CONNECTION
connectDB().then(() => {
    console.log('Database connected successfully');
}).catch((err) => {
    console.log('Error connecting to database:', err);
});

// Initialize Kafka service


const app = express();
const server = http.createServer(app);

// Initialize Socket.IO with CORS
const io = new Server(server, {
    cors: {
        origin: "*",
        methods: ["GET", "POST"]
    },
    transports: ['websocket']
});

// Store connected gateways
const connectedGateways = new Map();
// Initialize the gateway map in both controllers
initializeGatewayMap(connectedGateways);
initializeNodeController(connectedGateways);

// WebSocket connection handler
io.on('connection', (socket) => {
    console.log('New device connected:', socket.id);

    // Handle gateway registration
    socket.on('register_device', (data) => {
        const { gatewayId, ipAddress, port } = data;
        console.log(`Gateway ${gatewayId} registering...`);
        
        connectedGateways.set(gatewayId, {
            socket,
            status: 'available',
            enrolledAt: null,
            ipAddress,
            port
        });
        
        console.log(`Gateway ${gatewayId} registered successfully with IP: ${ipAddress}:${port}`);
    });

    // Handle disconnection
    socket.on('disconnect', () => {
        for (const [gatewayId, gateway] of connectedGateways.entries()) {
            if (gateway.socket === socket) {
                connectedGateways.delete(gatewayId);
                console.log(`Gateway ${gatewayId} disconnected`);
                break;
            }
        }
    });

    socket.on('gateway_response', (response) => {
        if (response.correlationId) {
            const callback = pendingCommands.get(response.correlationId);
            if (callback) {
                callback(response);
                pendingCommands.delete(response.correlationId);
            }
        }
    });
});

// Middlewares
app.use(cors());
app.use(express.json());
app.use(morgan("dev"));

// ROUTES
const gatewayRoutes = require("./routes/gatewayRoutes");
const nodeRoutes = require("./routes/nodeRoutes");
const authRoutes = require("./routes/userRoutes");
 
app.use("/api/v1/gateway", gatewayRoutes);
app.use("/api/v1/nodes", nodeRoutes);
app.use("/api/v1/auth", authRoutes);


// PORT for HTTP/WebSocket
const PORT = process.env.PORT || 5000;
const HOST = process.env.HOST || '0.0.0.0';

// Start MQTT Server on a different port
const MQTT_PORT = process.env.MQTT_PORT || 1884;
startMQTTServer(MQTT_PORT);

server.listen(PORT, HOST, () => {
    console.log(`Server is running on ${HOST}:${PORT}`.bgGreen.white);
});
