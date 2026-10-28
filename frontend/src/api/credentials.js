/**
 * User Credentials API Client
 * Handles GitHub Personal Access Token storage and management
 */
import apiClient from './axios';

/**
 * Store or update user's GitHub Personal Access Token
 * @param {Object} credentialsData - Credentials data
 * @param {string} credentialsData.github_token - GitHub Personal Access Token
 * @param {string} [credentialsData.scopes] - Token scopes (default: "repo")
 * @returns {Promise<Object>} Stored credentials (without token)
 */
export const storeCredentials = async (credentialsData) => {
    const response = await apiClient.post('/api/credentials/', credentialsData);
    return response.data;
};

/**
 * Get user's GitHub credentials info (without exposing the token)
 * @returns {Promise<Object>} Credentials metadata
 */
export const getCredentials = async () => {
    const response = await apiClient.get('/api/credentials/');
    return response.data;
};

/**
 * Update user's GitHub Personal Access Token
 * @param {Object} credentialsData - Credentials data
 * @param {string} credentialsData.github_token - GitHub Personal Access Token
 * @param {string} [credentialsData.scopes] - Token scopes
 * @returns {Promise<Object>} Updated credentials (without token)
 */
export const updateCredentials = async (credentialsData) => {
    const response = await apiClient.put('/api/credentials/', credentialsData);
    return response.data;
};

/**
 * Revoke user's GitHub credentials
 * @returns {Promise<void>}
 */
export const revokeCredentials = async () => {
    await apiClient.delete('/api/credentials/');
};

/**
 * Test if stored GitHub credentials are valid
 * @returns {Promise<Object>} Test result
 */
export const testCredentials = async () => {
    const response = await apiClient.post('/api/credentials/test');
    return response.data;
};
