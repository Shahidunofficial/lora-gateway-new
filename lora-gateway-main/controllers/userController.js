const User = require('../models/User');
const jwt = require('jsonwebtoken');
const { validationResult } = require('express-validator');

// Helper function to generate JWT token
const generateToken = (user) => {
    return jwt.sign(
        { 
            id: user._id,
            email: user.email,
            role: user.role 
        },
        process.env.JWT_SECRET,
        { expiresIn: '24h' }
    );
};

const userController = {
    // Register new user
    register: async (req, res) => {
        try {
            console.log('Received registration request:', req.body);
            
            const errors = validationResult(req);
            if (!errors.isEmpty()) {
                console.log('Validation errors:', errors.array());
                return res.status(400).json({ errors: errors.array() });
            }

            const { username, email, password } = req.body;

            // Log the extracted data
            console.log('Extracted data:', { username, email, password: '***' });

            // Check if user already exists
            let user = await User.findOne({ $or: [{ email }, { username }] });
            if (user) {
                return res.status(400).json({
                    message: 'User already exists with this email or username'
                });
            }

            // Create new user
            user = new User({
                username,
                email,
                password
            });

            await user.save();
            console.log('User saved successfully');

            // Generate token
            const token = generateToken(user);

            res.status(201).json({
                token,
                user: {
                    id: user._id,
                    username: user.username,
                    email: user.email,
                    role: user.role
                }
            });
        } catch (error) {
            console.error('Registration error details:', {
                message: error.message,
                stack: error.stack,
                name: error.name
            });
            res.status(500).json({ 
                message: 'Server error during registration',
                error: error.message 
            });
        }
    },

    // Login user
    login: async (req, res) => {
        try {
            const errors = validationResult(req);
            if (!errors.isEmpty()) {
                return res.status(400).json({ errors: errors.array() });
            }

            const { email, password } = req.body;

            // Find user
            const user = await User.findOne({ email });
            if (!user) {
                return res.status(401).json({ message: 'Invalid credentials' });
            }

            // Verify password
            const isMatch = await user.comparePassword(password);
            if (!isMatch) {
                return res.status(401).json({ message: 'Invalid credentials' });
            }

            try {
                // Generate token
                const token = generateToken(user);

                // Update last login
                user.last_login = Date.now();
                await user.save();

                res.json({
                    token,
                    user: {
                        id: user._id,
                        username: user.username,
                        email: user.email,
                        role: user.role
                    }
                });
            } catch (tokenError) {
                console.error('Token generation error:', tokenError);
                return res.status(500).json({ 
                    message: 'Error generating authentication token',
                    error: tokenError.message 
                });
            }
        } catch (error) {
            console.error('Login error:', error);
            res.status(500).json({ message: 'Server error during login' });
        }
    },

    // Get user profile
    getProfile: async (req, res) => {
        try {
            const user = await User.findById(req.user.id).select('-password');
            if (!user) {
                return res.status(404).json({ message: 'User not found' });
            }
            res.json(user);
        } catch (error) {
            console.error('Profile fetch error:', error);
            res.status(500).json({ message: 'Server error while fetching profile' });
        }
    },


   
};

module.exports = userController; 