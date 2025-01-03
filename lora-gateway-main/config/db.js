const mongoose = require("mongoose");
const colors = require("colors");

const connectDB = async () => {
  try {
    const connection = await mongoose.connect(process.env.MONGODB_URL);
    console.log(`Connected to MongoDB Database`.bgCyan.white);
    return connection;
  } catch (error) {
    console.log(`Error in MongoDB Connection ${error}`.bgRed.white);
    throw error;
  }
};

const getGatewayCollection = (gatewayId) => {
  try {
    const collectionName = `gateway_${gatewayId}_nodes`;
    return mongoose.connection.collection(collectionName);
  } catch (error) {
    console.log(`Error accessing gateway collection: ${error}`.bgRed.white);
    throw error;
  }
};

module.exports = { connectDB, getGatewayCollection };