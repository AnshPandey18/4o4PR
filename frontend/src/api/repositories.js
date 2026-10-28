/**
 * Repository API Client
 * Handles all repository-related API calls
 */
import apiClient from './axios';

/**
 * Get all repositories for the current user
 * @param {Object} params - Query parameters
 * @param {number} params.skip - Pagination offset (default: 0)
 * @param {number} params.limit - Max results (default: 100)
 * @returns {Promise<{total: number, repositories: Array}>}
 */
export const getRepositories = async ({ skip = 0, limit = 100 } = {}) => {
    const response = await apiClient.get('/api/repositories', {
        params: { skip, limit }
    });
    return response.data;
};

/**
 * Get a specific repository by ID
 * @param {number} id - Repository ID
 * @returns {Promise<Object>} Repository details
 */
export const getRepository = async (id) => {
    const response = await apiClient.get(`/api/repositories/${id}`);
    return response.data;
};

/**
 * Add a new repository
 * @param {Object} data - Repository data
 * @param {string} data.url - GitHub repository URL
 * @param {string} data.branch - Branch name (default: 'main')
 * @param {string} [data.personal_access_token] - GitHub PAT (for private repos)
 * @param {string} [data.description] - Repository description
 * @returns {Promise<Object>} Created repository
 */
export const createRepository = async (data) => {
    const response = await apiClient.post('/api/repositories', data);
    return response.data;
};

/**
 * Onboard a new repository (clone and register in one operation)
 * This is the unified endpoint for the "Run Pipeline" workflow.
 * @param {Object} data - Repository data
 * @param {string} data.url - GitHub repository URL
 * @param {string} data.branch - Branch name (default: 'main')
 * @param {string} [data.personal_access_token] - GitHub PAT (for private repos)
 * @returns {Promise<Object>} Onboarded repository with clone status
 */
export const onboardRepository = async (data) => {
    const response = await apiClient.post('/api/repositories/onboard', data);
    return response.data;
};

/**
 * Update repository information
 * @param {number} id - Repository ID
 * @param {Object} updates - Fields to update
 * @param {string} [updates.branch] - Branch name
 * @param {string} [updates.description] - Description
 * @param {boolean} [updates.is_active] - Active status
 * @returns {Promise<Object>} Updated repository
 */
export const updateRepository = async (id, updates) => {
    const response = await apiClient.patch(`/api/repositories/${id}`, updates);
    return response.data;
};

/**
 * Delete a repository
 * @param {number} id - Repository ID
 * @param {boolean} deleteClone - Also delete cloned files (default: false)
 * @returns {Promise<void>}
 */
export const deleteRepository = async (id, deleteClone = false) => {
    await apiClient.delete(`/api/repositories/${id}`, {
        params: { delete_clone: deleteClone }
    });
};

/**
 * Clone a repository
 * @param {number} id - Repository ID
 * @param {Object} options - Clone options
 * @param {string} [options.branch] - Branch to clone
 * @param {boolean} [options.force] - Force reclone (default: false)
 * @returns {Promise<Object>} Clone result with path and size
 */
export const cloneRepository = async (id, { branch, force = false } = {}) => {
    const response = await apiClient.post(`/api/repositories/${id}/clone`, {
        branch,
        force
    });
    return response.data;
};

/**
 * Get clone status for a repository
 * @param {number} id - Repository ID
 * @returns {Promise<Object>} Clone status and metadata
 */
export const getCloneStatus = async (id) => {
    const response = await apiClient.get(`/api/repositories/${id}/clone/status`);
    return response.data;
};

/**
 * Delete cloned repository files
 * @param {number} id - Repository ID
 * @returns {Promise<void>}
 */
export const deleteClone = async (id) => {
    await apiClient.delete(`/api/repositories/${id}/clone`);
};

/**
 * Get Redis cache statistics
 * @returns {Promise<Object>} Cache stats including hit rate
 */
export const getCacheStats = async () => {
    const response = await apiClient.get('/api/repositories/cache/stats');
    return response.data;
};

/**
 * Flush all cache entries (admin operation)
 * @returns {Promise<void>}
 */
export const flushCache = async () => {
    await apiClient.delete('/api/repositories/cache/flush');
};

/**
 * Fetch repository information from GitHub (using stored PAT)
 * @param {string} url - GitHub repository URL
 * @returns {Promise<Object>} Repository metadata
 */
export const fetchRepositoryInfo = async (url) => {
    const response = await apiClient.post('/api/repositories/fetch-info', null, {
        params: { repo_url: url }
    });
    return response.data;
};
