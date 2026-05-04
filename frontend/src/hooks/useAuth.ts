import { useState, useEffect, useCallback } from 'react';
import vkBridge from '@vkontakte/vk-bridge';
import WebApp from '@twa-dev/sdk';
import { authApi } from '../api/client';

export function useAuth() {
    const [user, setUser] = useState<any>(null);
    const [token, setToken] = useState<string | null>(localStorage.getItem('ff_token'));
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [needsLogin, setNeedsLogin] = useState(false);

    const loginWithPassword = async (telegramId: number, password: string) => {
        setIsLoading(true);
        try {
            const data = await authApi.loginWithPassword(telegramId, password);
            localStorage.setItem('ff_token', data.access_token);
            setToken(data.access_token);
            const fullUser = await authApi.getMe();
            setUser(fullUser);
            setNeedsLogin(false);
            setError(null);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Неверный ID или пароль');
            throw err;
        } finally {
            setIsLoading(false);
        }
    };

    const loginWithEmail = async (email: string, password: string) => {
        setIsLoading(true);
        try {
            const data = await authApi.loginWithEmail(email, password);
            localStorage.setItem('ff_token', data.access_token);
            setToken(data.access_token);
            const fullUser = await authApi.getMe();
            setUser(fullUser);
            setNeedsLogin(false);
            setError(null);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка входа');
            throw err;
        } finally {
            setIsLoading(false);
        }
    };

    const registerWithEmail = async (email: string, password: string, name: string) => {
        setIsLoading(true);
        try {
            const data = await authApi.registerWithEmail(email, password, name);
            localStorage.setItem('ff_token', data.access_token);
            setToken(data.access_token);
            const fullUser = await authApi.getMe();
            setUser(fullUser);
            setNeedsLogin(false);
            setError(null);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Ошибка регистрации');
            throw err;
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        let attempts = 0;
        const maxAttempts = 10;

        const checkAuth = async () => {
            try {
                attempts++;
                const urlParams = new URLSearchParams(window.location.search);
                const urlToken = urlParams.get('token');

                // 1. Check for token in URL (Magic link)
                if (urlToken) {
                    console.log('[Auth] Token found in URL');
                    localStorage.setItem('ff_token', urlToken);
                    setToken(urlToken);
                    try {
                        const fullUser = await authApi.getMe();
                        setUser(fullUser);
                        setIsLoading(false);
                        return;
                    } catch (err) {
                        console.error('[Auth] URL token invalid');
                        localStorage.removeItem('ff_token');
                        setToken(null);
                    }
                }

                // --- VK MINI APP: detect VK launch params ---
                const vkUserId = urlParams.get('vk_user_id');
                if (vkUserId) {
                    console.log('[Auth] VK launch parameters detected!');
                    const vkParams: Record<string, string> = {};
                    urlParams.forEach((value, key) => {
                        vkParams[key] = value;
                    });

                    try {
                        // Get VK user info for proper name display
                        const vkUserInfo = await Promise.race([
                            vkBridge.send('VKWebAppGetUserInfo'),
                            new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 1500))
                        ]).catch(() => null) as any;
                        const authData = await authApi.vkLogin(vkParams, vkUserInfo?.first_name, vkUserInfo?.last_name);
                        if (authData.access_token) {
                            localStorage.setItem('ff_token', authData.access_token);
                            setToken(authData.access_token);

                            const fullUser = await authApi.getMe();
                            setUser(fullUser);
                            setIsLoading(false);
                            return;
                        } else {
                            console.error('[Auth] VK Login failed: No access token');
                            setNeedsLogin(true);
                        }
                    } catch (vkErr: any) {
                        console.error('[Auth] VK Login Exception:', vkErr);
                        setError(vkErr.response?.data?.detail || vkErr.message || 'VK Auth Error');
                    }
                    setIsLoading(false);
                    return;
                }

                // --- SAVED TOKEN: check if localStorage has a valid token ---
                const savedToken = localStorage.getItem('ff_token');
                if (savedToken && !urlToken) {
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
                    }
                }

                // --- MOCK / DEBUG BYPASS ---
                if (urlParams.get('mock') === '1') {
                    setUser({ id: 1, first_name: 'Mock User' });
                    setIsLoading(false);
                    return;
                }

                // 2. Fallback to Telegram Web App
                const tg = (window as any).Telegram?.WebApp || WebApp;
                if (tg && tg.initData) {
                    tg.ready();
                    const tgUser = tg.initDataUnsafe?.user;
                    if (tgUser) {
                        try {
                            const authData = await authApi.login(tgUser.id, tgUser.username);
                            if (authData.access_token) {
                                localStorage.setItem('ff_token', authData.access_token);
                                setToken(authData.access_token);
                                const fullUser = await authApi.getMe();
                                setUser(fullUser);
                                setIsLoading(false);
                                return;
                            }
                        } catch (err) {
                            console.error('[Auth] TG Login failed');
                        }
                    }
                }

                // Retry or show login
                if (attempts < maxAttempts) {
                    setTimeout(checkAuth, 200);
                } else {
                    setNeedsLogin(true);
                    setIsLoading(false);
                }
            } catch (globalErr: any) {
                console.error('[Auth] Global Crash:', globalErr);
                setError(`Crash: ${globalErr.message || 'Unknown'}`);
                setIsLoading(false);
            }
        };

        checkAuth();

        // Safety timeout: force loading=false after 5s
        const panicTimer = setTimeout(() => {
            setIsLoading(prev => {
                if (prev) {
                    console.warn('[Auth] Panic timer triggered');
                    return false;
                }
                return prev;
            });
        }, 2500);

        return () => clearTimeout(panicTimer);
    }, []);

    const refreshUser = useCallback(async () => {
        try {
            const freshUser = await authApi.getMe();
            setUser(freshUser);
        } catch (err) {
            console.error('[Auth] refreshUser failed:', err);
        }
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
        isFree,
        refreshUser
    };
}
