/**
 * Pipeline Runs API Client
 * Handles all pipeline run-related API calls
 */
import apiClient from './axios';

/**
 * Get all pipeline runs for the current user
 * @param {Object} params - Query parameters
 * @param {number} [params.repository_id] - Filter by repository
 * @param {string} [params.status] - Filter by status
 * @param {number} params.skip - Pagination offset (default: 0)
 * @param {number} params.limit - Max results (default: 100)
 * @returns {Promise<{total: number, runs: Array}>}
 */
export const getPipelineRuns = async ({
    repository_id,
    status,
    skip = 0,
    limit = 100
} = {}) => {
    const response = await apiClient.get('/api/pipeline-runs', {
        params: {
            repository_id,
            status,
            skip,
            limit
        }
    });
    return response.data;
};

/**
 * Get a specific pipeline run by run_id
 * @param {string} runId - Pipeline run ID
 * @returns {Promise<Object>} Pipeline run details
 */
export const getPipelineRun = async (runId) => {
    const response = await apiClient.get(`/api/pipeline-runs/${runId}`);
    return response.data;
};

/**
 * Trigger a new pipeline run
 * @param {Object} data - Pipeline run configuration
 * @param {number} data.repository_id - Repository to analyze
 * @param {string} [data.import_roots] - Comma-separated import roots (default: 'src')
 * @param {boolean} [data.verbose] - Enable verbose output (default: true)
 * @param {boolean} [data.force_reclone] - Force reclone repository (default: false)
 * @returns {Promise<Object>} Trigger response with run_id
 */
export const triggerPipelineRun = async (data) => {
    const response = await apiClient.post('/api/pipeline-runs/trigger', data);
    return response.data;
};

/**
 * Create a pipeline run record (typically used by orchestrator)
 * @param {Object} data - Pipeline run data
 * @param {number} data.repository_id - Repository ID
 * @param {string} [data.import_roots] - Import roots
 * @param {string} [data.output_dir] - Output directory
 * @param {string} [data.config_file] - Config file path
 * @param {boolean} [data.verbose] - Verbose mode
 * @returns {Promise<Object>} Created pipeline run
 */
export const createPipelineRun = async (data) => {
    const response = await apiClient.post('/api/pipeline-runs', data);
    return response.data;
};

/**
 * Update pipeline run status and results
 * @param {string} runId - Pipeline run ID
 * @param {Object} updates - Fields to update
 * @param {string} [updates.status] - New status
 * @param {number} [updates.bugs_detected] - Number of bugs detected
 * @param {number} [updates.bugs_fixed] - Number of bugs fixed
 * @param {number} [updates.patches_generated] - Number of patches generated
 * @param {string} [updates.error_message] - Error message (if failed)
 * @param {string} [updates.error_traceback] - Full error traceback
 * @returns {Promise<Object>} Updated pipeline run
 */
export const updatePipelineRun = async (runId, updates) => {
    const response = await apiClient.patch(`/api/pipeline-runs/${runId}`, updates);
    return response.data;
};

/**
 * Delete a pipeline run
 * @param {string} runId - Pipeline run ID
 * @returns {Promise<void>}
 */
export const deletePipelineRun = async (runId) => {
    await apiClient.delete(`/api/pipeline-runs/${runId}`);
};

/**
 * Cancel a running pipeline
 * @param {string} runId - Pipeline run ID
 * @param {string} [reason] - Cancellation reason
 * @returns {Promise<Object>} Cancellation response
 */
export const cancelPipelineRun = async (runId, reason) => {
    const response = await apiClient.post(`/api/pipeline-runs/${runId}/cancel`, {
        reason
    });
    return response.data;
};

/**
 * Get aggregate statistics for pipeline runs
 * @param {number} [repositoryId] - Filter by repository
 * @returns {Promise<Object>} Statistics summary
 */
export const getPipelineRunStats = async (repositoryId) => {
    const response = await apiClient.get('/api/pipeline-runs/stats/summary', {
        params: { repository_id: repositoryId }
    });
    return response.data;
};

/**
 * Poll pipeline run status until completion
 * @param {string} runId - Pipeline run ID
 * @param {Function} onUpdate - Callback function called on each update
 * @param {number} intervalMs - Polling interval in milliseconds (default: 2000)
 * @returns {Promise<Object>} Final pipeline run state
 */
export const pollPipelineRun = async (runId, onUpdate, intervalMs = 2000) => {
    return new Promise((resolve, reject) => {
        const poll = async () => {
            try {
                const run = await getPipelineRun(runId);
                
                // Call update callback
                if (onUpdate) {
                    onUpdate(run);
                }
                
                // Check if finished
                if (['completed', 'failed', 'cancelled'].includes(run.status)) {
                    resolve(run);
                    return;
                }
                
                // Continue polling
                setTimeout(poll, intervalMs);
            } catch (error) {
                reject(error);
            }
        };
        
        poll();
    });
};

/**
 * Status helpers
 */
export const RunStatus = {
    PENDING: 'pending',
    QUEUED: 'queued',
    RUNNING: 'running',
    COMPLETED: 'completed',
    FAILED: 'failed',
    CANCELLED: 'cancelled',
    
    isFinished: (status) => ['completed', 'failed', 'cancelled'].includes(status),
    isActive: (status) => ['pending', 'queued', 'running'].includes(status),
    
    getColor: (status) => {
        const colors = {
            pending: '#ffb764',
            queued: '#20c2a4',
            running: '#4d9eff',
            completed: '#20c2a4',
            failed: '#e6714f',
            cancelled: '#888'
        };
        return colors[status] || '#888';
    },
    
    getLabel: (status) => {
        const labels = {
            pending: 'Pending',
            queued: 'Queued',
            running: 'Running',
            completed: 'Completed',
            failed: 'Failed',
            cancelled: 'Cancelled'
        };
        return labels[status] || status;
    }
};
