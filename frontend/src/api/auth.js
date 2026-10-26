/**
 * Authentication API Client
 * Handles user registration, login, and token management
 */
import apiClient from './axios';

/**
 * Register a new user
 * @param {Object} userData - User registration data
 * @param {string} userData.email - User email
 * @param {string} userData.password - User password
 * @param {string} userData.full_name - User's full name
 * @returns {Promise<Object>} Created user
 */
export const register = async (userData) => {
    const response = await apiClient.post('/api/auth/register', userData);
    return response.data;
};

/**
 * Login user and get JWT token
 * @param {Object} credentials - Login credentials
 * @param {string} credentials.email - User email
 * @param {string} credentials.password - User password
 * @returns {Promise<{access_token: string, token_type: string}>}
 */
export const login = async (credentials) => {
    const response = await apiClient.post('/api/auth/login', credentials);
    const { access_token, token_type } = response.data;
    
    // Store token in localStorage
    localStorage.setItem('token', access_token);
    localStorage.setItem('token_type', token_type);
    
    return response.data;
};

/**
 * Logout user (clear token)
 */
export const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('token_type');
    localStorage.removeItem('user');
    window.location.href = '/login';
};

/**
 * Get current user profile
 * @returns {Promise<Object>} User profile
 */
export const getCurrentUser = async () => {
    const response = await apiClient.get('/api/users/me');
    
    // Cache user in localStorage
    localStorage.setItem('user', JSON.stringify(response.data));
    
    return response.data;
};

/**
 * Check if user is authenticated
 * @returns {boolean}
 */
export const isAuthenticated = () => {
    return !!localStorage.getItem('token');
};

/**
 * Get stored token
 * @returns {string|null}
 */
export const getToken = () => {
    return localStorage.getItem('token');
};

/**
 * Get cached user from localStorage
 * @returns {Object|null}
 */
export const getCachedUser = () => {
    const userStr = localStorage.getItem('user');
    return userStr ? JSON.parse(userStr) : null;
};
