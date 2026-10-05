import apiClient from '../api/axios';

const authService = {
    async register(email, password, fullName) {
        const response = await apiClient.post('/api/auth/register', {
            email,
            password,
            full_name: fullName,
        });
        return response.data;
    },

    async login(email, password) {
        const response = await apiClient.post('/api/auth/login', {
            email,
            password,
        });
        const { access_token } = response.data;
        localStorage.setItem('token', access_token);
        return response.data;
    },

    logout() {
        localStorage.removeItem('token');
    },

    isAuthenticated() {
        return !!localStorage.getItem('token');
    },

    async getCurrentUser() {
        const response = await apiClient.get('/api/users/me');
        return response.data;
    },
};

export default authService;
