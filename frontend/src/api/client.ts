import axios from 'axios';

const API_BASE_URL = '/api'; // Use relative path since we are on the same domain

const apiClient = axios.create({
    baseURL: API_BASE_URL,
});

// Request interceptor to add JWT token if available
apiClient.interceptors.request.use((config) => {
    const token = localStorage.getItem('ff_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export const authApi = {
    login: async (telegramId: number, username?: string) => {
        // We use /register because it handles both creation and token generation
        const response = await apiClient.post('/auth/register', {
            telegram_id: telegramId,
            username: username || `user_${telegramId}`,
        });
        return response.data; // Returns { access_token: "..." }
    },
    getMe: async () => {
        const response = await apiClient.get('/auth/me');
        return response.data;
    },
};

export const fridgeApi = {
    getProducts: async () => {
        const response = await apiClient.get('/products');
        return response.data;
    },
    addProduct: async (data: any) => {
        const response = await apiClient.post('/products', data);
        return response.data;
    },
    deleteProduct: async (id: number) => {
        await apiClient.delete(`/products/${id}`);
    },
    consumeProduct: async (id: number, data: { amount: number; unit: 'grams' | 'qty' }) => {
        const response = await apiClient.post(`/products/${id}/consume`, data);
        return response.data;
    }
};

export const smartApi = {
    analyze: async (text: string) => {
        const response = await apiClient.post('/smart/analyze', { text });
        return response.data;
    }
};

export const searchApi = {
    fridge: async (q?: string, withSummary: boolean = false) => {
        const response = await apiClient.get('/search/fridge', { params: { q, with_summary: withSummary } });
        return response.data;
    }
};

export const herbalifeApi = {
    search: async (q: string) => {
        const response = await apiClient.get('/herbalife/search', { params: { q } });
        return response.data;
    },
    calculate: async (productId: string, amount: number, unit: string) => {
        const response = await apiClient.post('/herbalife/calculate', { product_id: productId, amount, unit });
        return response.data;
    }
};

export const universalApi = {
    process: async (input: { text?: string, file?: Blob }) => {
        const formData = new FormData();
        if (input.text) formData.append('text', input.text);
        if (input.file) {
            let fileName = 'file';
            if (input.file.type.includes('audio')) fileName = 'voice.webm';
            else if (input.file.type.includes('video')) fileName = 'voice.webm'; // MediaRecorder often uses video/webm
            else if (input.file.type.includes('image')) fileName = 'image.jpg';
            formData.append('file', input.file, fileName);
        }
        const response = await apiClient.post('/universal/process', formData);
        return response.data;
    }
};

export const shoppingApi = {
    getList: async () => {
        const response = await apiClient.get('/shopping-list');
        return response.data;
    },
    addItem: async (productName: string) => {
        const response = await apiClient.post('/shopping-list', { product_name: productName });
        return response.data;
    },
    toggleBought: async (id: number) => {
        const response = await apiClient.post(`/shopping-list/${id}/buy`);
        return response.data;
    },
    deleteItem: async (id: number) => {
        await apiClient.delete(`/shopping-list/${id}`);
    }
};

export const consumptionApi = {
    getLogs: async (days: number = 7) => {
        const response = await apiClient.get('/consumption', { params: { days } });
        return response.data;
    },
    manualLog: async (data: any) => {
        const response = await apiClient.post('/consumption/manual', data);
        return response.data;
    }
};

export const statsApi = {
    getDailyReport: async () => {
        const response = await apiClient.get('/reports/daily');
        return response.data;
    },
};

export default apiClient;
