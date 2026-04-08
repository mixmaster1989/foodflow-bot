import { useState, useEffect, useCallback } from 'react';
import WebApp from '@twa-dev/sdk';
import { authApi } from '../api/client';

export function useAuth() {
    const [user, setUser] = useState<any>(null);
    const [token, setToken] = useState<string | null>(localStorage.getItem('ff_token'));
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [needsLogin, setNeedsLogin] = useState(false);

    // Manual login function (for LoginView)
    const loginWithPassword = useCallback(async (telegramId: number, password: string) => {
        const authData = await authApi.loginWithPassword(telegramId, password);
        if (authData.access_token) {
            localStorage.setItem('ff_token', authData.access_token);
            setToken(authData.access_token);

            const fullUser = await authApi.getMe();
            setUser(fullUser);
            setNeedsLogin(false);
            setError(null);
        }
    }, []);

    const loginWithEmail = useCallback(async (email: string, password: string) => {
        const authData = await authApi.loginWithEmail(email, password);
        if (authData.access_token) {
            localStorage.setItem('ff_token', authData.access_token);
            setToken(authData.access_token);
            const fullUser = await authApi.getMe();
            setUser(fullUser);
            setNeedsLogin(false);
            setError(null);
        }
    }, []);

    const registerWithEmail = useCallback(async (email: string, password: string, name: string) => {
        const authData = await authApi.registerWithEmail(email, password, name);
        if (authData.access_token) {
            localStorage.setItem('ff_token', authData.access_token);
            setToken(authData.access_token);
            const fullUser = await authApi.getMe();
            setUser(fullUser);
            setNeedsLogin(false);
            setError(null);
        }
    }, []);

    useEffect(() => {
        let attempts = 0;
        const maxAttempts = 20; // 20 * 150ms = 3 seconds

        const checkAuth = async () => {
            attempts++;
            console.log(`[Auth] Check attempt ${attempts}...`);

            // --- MAGIC LINK: token from URL query param or hash ---
            const urlParams = new URLSearchParams(window.location.search);
            let urlToken = urlParams.get('token');

            // Also check hash (common for VK/fragment transitions)
            if (!urlToken && window.location.hash.includes('token=')) {
                const hashParams = new URLSearchParams(window.location.hash.substring(1));
                urlToken = hashParams.get('token');
            }

            if (urlToken) {
                console.log('[Auth] Magic link token detected!');
                localStorage.setItem('ff_token', urlToken);
                setToken(urlToken);


                // Clean URL so token isn't visible / shareable
                window.history.replaceState({}, '', window.location.pathname);

                try {
                    const fullUser = await authApi.getMe();
                    setUser(fullUser);
                } catch (err) {
                    console.error('[Auth] Magic link token invalid:', err);
                    localStorage.removeItem('ff_token');
                    setToken(null);
                    setNeedsLogin(true);
                }
                setIsLoading(false);
                return;
            }

            // --- SAVED TOKEN: check if localStorage has a valid token ---
            const savedToken = localStorage.getItem('ff_token');
            if (savedToken && !urlToken) {
                // Try to use existing token (works for returning web users)
                try {
                    const fullUser = await authApi.getMe();
                    setUser(fullUser);
                    setToken(savedToken);
                    setIsLoading(false);
                    return;
                } catch (err) {
                    console.warn('[Auth] Saved token expired, clearing...');
                    localStorage.removeItem('ff_token');
                    setToken(null);
                    // Fall through to Telegram check
                }
            }

            // --- MOCK / DEBUG BYPASS ---
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
                    setNeedsLogin(true);
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

                        try {
                            const fullUser = await authApi.getMe();
                            setUser(fullUser);
                        } catch (getMeErr) {
                            console.error('[Auth] Failed to fetch full profile:', getMeErr);
                            setUser(tgUser);
                        }
                    } else {
                        setUser(tgUser);
                    }
                } catch (apiErr: any) {
                    const msg = apiErr.response?.data?.detail || apiErr.message || 'API Connection Error';
                    setError(`Backend Connection Failure: ${msg}`);
                }

                setIsLoading(false);
                return;
            }

            // If no data yet, retry or show login form
            if (attempts < maxAttempts) {
                setTimeout(checkAuth, 150);
            } else {
                // No Telegram, no saved token — show login form
                console.log('[Auth] No Telegram SDK, showing login form');
                setNeedsLogin(true);
                setIsLoading(false);
            }
        };

        checkAuth();
    }, []);

    const isCurator = user?.tier === 'curator' || user?.role === 'curator';
    const isAdmin = user?.role === 'admin';
    const isPro = user?.tier === 'pro' || isCurator || isAdmin;
    const isBasic = user?.tier === 'basic' || isPro;
    const isFree = !isBasic;

    return {
        user,
        token,
        isLoading,
        error,
        needsLogin,
        loginWithPassword,
        loginWithEmail,
        registerWithEmail,
        isCurator,
        isAdmin,
        isPro,
        isBasic,
        isFree
    };
}
