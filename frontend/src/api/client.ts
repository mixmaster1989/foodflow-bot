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
    loginWithPassword: async (telegramId: number, password: string) => {
        const response = await apiClient.post('/auth/login-password', {
            telegram_id: telegramId,
            password: password,
        });
        return response.data; // Returns { access_token: "..." }
    },
    loginWithEmail: async (email: string, password: string) => {
        const response = await apiClient.post('/auth/web-login', { email, password });
        return response.data; // Returns { access_token: "..." }
    },
    registerWithEmail: async (email: string, password: string, name: string) => {
        const response = await apiClient.post('/auth/web-register', { email, password, name });
        return response.data; // Returns { access_token: "..." }
    },
    vkLogin: async (params: Record<string, string>, firstName?: string, lastName?: string) => {
        const response = await apiClient.post('/auth/vk-login', {
            params,
            first_name: firstName,
            last_name: lastName
        });
        return response.data; // Returns { access_token: "..." }
    },
    syncProfile: async (firstName?: string, lastName?: string) => {
        const response = await apiClient.post('/auth/sync-profile', {
            first_name: firstName,
            last_name: lastName
        });
        return response.data;
    },
    getMe: async () => {
        const response = await apiClient.get('/auth/me');
        return response.data;
    },
    updateSettings: async (settings: any) => {
        const response = await apiClient.patch('/auth/settings', settings);
        return response.data;
    }
};

export const fridgeApi = {
    getProducts: async (params?: { query?: string; page?: number; page_size?: number }) => {
        const response = await apiClient.get('/products', { params });
        return response.data;
    },
    getSummary: async () => {
        const response = await apiClient.get('/products/summary');
        return response.data;
    },
    scanLabel: async (file: Blob) => {
        const formData = new FormData();
        formData.append('file', file, 'label.jpg');
        const response = await apiClient.post('/products/scan-label', formData);
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
    getProducts: async () => {
        const response = await apiClient.get('/herbalife/products');
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
    getLogs: async (params?: { days?: number, date?: string }) => {
        const response = await apiClient.get('/consumption', { params });
        return response.data;
    },
    manualLog: async (data: any) => {
        const response = await apiClient.post('/consumption/manual', data);
        return response.data;
    },
    updateLog: async (id: number, data: any) => {
        const response = await apiClient.patch(`/consumption/${id}`, data);
        return response.data;
    },
    deleteLog: async (id: number) => {
        await apiClient.delete(`/consumption/${id}`);
    }
};

export const waterApi = {
    getLogs: async (date?: string) => {
        const response = await apiClient.get('/water', { params: { date } });
        return response.data;
    },
    logWater: async (amount: number) => {
        const response = await apiClient.post('/water', { amount_ml: amount });
        return response.data;
    },
    deleteWater: async (id: number) => {
        await apiClient.delete(`/water/${id}`);
    }
};

export const recipesApi = {
    getCategories: async () => {
        const response = await apiClient.get('/recipes/categories');
        return response.data;
    },
    generateRecipes: async (category: string, refresh: boolean = false) => {
        const response = await apiClient.post('/recipes/generate', { category, refresh });
        return response.data;
    }
};

export const statsApi = {
    getDailyReport: async (date?: string) => {
        const response = await apiClient.get('/reports/daily', { params: { date } });
        return response.data;
    }
};

export const referralsApi = {
    getMe: async () => {
        const response = await apiClient.get('/referrals/me');
        return response.data;
    },
    generateLink: async (days?: number) => {
        const response = await apiClient.post('/referrals/generate_link', { days });
        return response.data;
    },
    activateReward: async (rewardId: number) => {
        const response = await apiClient.post('/referrals/activate_reward', { reward_id: rewardId });
        return response.data;
    }
};

export const weightApi = {
    getLogs: async (limit: number = 30) => {
        const response = await apiClient.get('/weight', { params: { limit } });
        return response.data;
    },
    logWeight: async (weight: number) => {
        const response = await apiClient.post('/weight', { weight });
        return response.data;
    }
};

export const receiptsApi = {
    upload: async (file: Blob) => {
        const formData = new FormData();
        formData.append('file', file, 'receipt.jpg');
        const response = await apiClient.post('/receipts/upload', formData);
        return response.data;
    },
    addItem: async (receiptId: number, itemData: any) => {
        const response = await apiClient.post(`/receipts/${receiptId}/items/add`, itemData);
        return response.data;
    }
};

export const savedDishesApi = {
    getList: async () => {
        const response = await apiClient.get('/saved-dishes');
        return response.data;
    },
    create: async (data: any) => {
        const response = await apiClient.post('/saved-dishes', data);
        return response.data;
    },
    delete: async (id: number) => {
        await apiClient.delete(`/saved-dishes/${id}`);
    },
    log: async (id: number, date?: string) => {
        const response = await apiClient.post(`/saved-dishes/${id}/log`, { date });
        return response.data;
    }
};

export default apiClient;
