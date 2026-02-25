import { useState, useEffect } from 'react';
import WebApp from '@twa-dev/sdk';
import { authApi } from '../api/client';

export function useAuth() {
    const [user, setUser] = useState<any>(null);
    const [token, setToken] = useState<string | null>(localStorage.getItem('ff_token'));
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let attempts = 0;
        const maxAttempts = 20; // 20 * 150ms = 3 seconds

        const checkAuth = async () => {
            attempts++;
            console.log(`[Auth] Check attempt ${attempts}...`);

            // --- MOCK / DEBUG BYPASS ---
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.get('mock') === '1') {
                console.warn('[Auth] Mock mode enabled');
                const mockUser = {
                    id: 495294354,
                    username: 'mock_user',
                    first_name: 'Mock',
                    last_name: 'Tester'
                };
                setUser(mockUser);
                setIsLoading(false);
                return;
            }

            // Get TG Object
            const tg = (window as any).Telegram?.WebApp || WebApp;

            // Check if we have valid initData (crucial!)
            if (tg && tg.initData) {
                console.log('[Auth] Valid SDK data detected!');
                tg.ready();
                tg.expand();

                const tgUser = tg.initDataUnsafe?.user;
                if (!tgUser) {
                    // initData exists but user is missing? Weird but possible.
                    setError(`Auth Error: initData present, but user is null.`);
                    setIsLoading(false);
                    return;
                }

                console.log('[Auth] User detected:', tgUser.id);
                setUser(tgUser);

                try {
                    const authData = await authApi.login(tgUser.id, tgUser.username);
                    if (authData.access_token) {
                        localStorage.setItem('ff_token', authData.access_token);
                        setToken(authData.access_token);
                    }
                } catch (apiErr: any) {
                    const msg = apiErr.response?.data?.detail || apiErr.message || 'API Connection Error';
                    setError(`Backend Connection Failure: ${msg}`);
                }

                setIsLoading(false);
                return;
            }

            // If no data yet, retry or fail
            if (attempts < maxAttempts) {
                setTimeout(checkAuth, 150);
            } else {
                // Final failure
                const rawHash = window.location.hash;
                const rawSearch = window.location.search;
                const debugStr = `Hash: ${rawHash.substring(0, 50)}...\nSearch: ${rawSearch}\nSDK Data: ${tg?.initData ? 'yes' : 'no'}\nTG Obj: ${!!tg}`;

                console.error('[Auth] Timeout waiting for Telegram SDK');
                setError(`Auth Timeout (v3).\nTelegram did not provide data in time.\n\n${debugStr}`);
                setIsLoading(false);
            }
        };

        checkAuth();
    }, []);

    return { user, token, isLoading, error };
}
