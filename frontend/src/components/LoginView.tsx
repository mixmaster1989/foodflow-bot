import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

type TabType = 'telegram' | 'email' | 'register';

interface LoginViewProps {
    onLogin: (telegramId: number, password: string) => Promise<void>;
    onLoginEmail?: (email: string, password: string) => Promise<void>;
    onRegister?: (email: string, password: string, name: string) => Promise<void>;
}

export function LoginView({ onLogin, onLoginEmail, onRegister }: LoginViewProps) {
    const [activeTab, setActiveTab] = useState<TabType>('email');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    // Telegram tab state
    const [telegramId, setTelegramId] = useState('');
    const [tgPassword, setTgPassword] = useState('');

    // Email/Register shared state
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [name, setName] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');

    const handleTelegramSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        const id = parseInt(telegramId, 10);
        if (isNaN(id)) { setError('Введите корректный Telegram ID (число)'); return; }
        setIsLoading(true);
        try {
            await onLogin(id, tgPassword);
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message || 'Ошибка соединения');
        } finally {
            setIsLoading(false);
        }
    };

    const handleEmailLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        if (!onLoginEmail) return;
        setIsLoading(true);
        try {
            await onLoginEmail(email, password);
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message || 'Ошибка входа');
        } finally {
            setIsLoading(false);
        }
    };

    const handleRegister = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        if (!onRegister) return;
        if (password !== confirmPassword) { setError('Пароли не совпадают'); return; }
        if (password.length < 6) { setError('Пароль должен быть не короче 6 символов'); return; }
        setIsLoading(true);
        try {
            await onRegister(email, password, name);
            setSuccess('🎉 Добро пожаловать! Вы получили 3 дня PRO в подарок!');
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message || 'Ошибка регистрации');
        } finally {
            setIsLoading(false);
        }
    };

    const tabs: { key: TabType; label: string; emoji: string }[] = [
        { key: 'email', label: 'Вход', emoji: '✉️' },
        { key: 'register', label: 'Регистрация', emoji: '🚀' },
        { key: 'telegram', label: 'Telegram ID', emoji: '🤖' },
    ];

    return (
        <div className="min-h-screen bg-neutral-950 flex flex-col items-center justify-center p-6">
            <motion.div
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6 }}
                className="w-full max-w-sm"
            >
                {/* Logo */}
                <div className="text-center mb-8">
                    <h1 className="text-4xl font-black bg-gradient-to-r from-green-400 to-emerald-500 bg-clip-text text-transparent">
                        FoodFlow
                    </h1>
                    <p className="text-neutral-500 text-sm mt-2">Умный дневник питания</p>
                </div>

                {/* Tabs */}
                <div className="flex bg-white/5 rounded-2xl p-1 mb-6 gap-1">
                    {tabs.map(tab => (
                        <button
                            key={tab.key}
                            onClick={() => { setActiveTab(tab.key); setError(null); setSuccess(null); }}
                            className={`flex-1 py-2 px-1 rounded-xl text-xs font-semibold transition-all duration-200 ${activeTab === tab.key
                                    ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-500/20'
                                    : 'text-neutral-500 hover:text-neutral-300'
                                }`}
                        >
                            {tab.emoji} {tab.label}
                        </button>
                    ))}
                </div>

                {/* Error / Success banners */}
                <AnimatePresence>
                    {error && (
                        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
                            className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl">
                            <p className="text-red-400 text-sm text-center">{error}</p>
                        </motion.div>
                    )}
                    {success && (
                        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
                            className="mb-4 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
                            <p className="text-emerald-400 text-sm text-center">{success}</p>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Tab Content */}
                <AnimatePresence mode="wait">
                    {activeTab === 'email' && (
                        <motion.form key="email" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 10 }}
                            onSubmit={handleEmailLogin} className="space-y-4">
                            <div>
                                <label className="block text-neutral-400 text-xs font-medium mb-1.5 uppercase tracking-wider">Email</label>
                                <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                                    placeholder="your@email.com" required
                                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-neutral-600 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 transition-all" />
                            </div>
                            <div>
                                <label className="block text-neutral-400 text-xs font-medium mb-1.5 uppercase tracking-wider">Пароль</label>
                                <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                                    placeholder="Ваш пароль" required
                                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-neutral-600 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 transition-all" />
                            </div>
                            <button type="submit" disabled={isLoading}
                                className="w-full py-3.5 bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-500 hover:to-green-500 text-white font-bold rounded-xl transition-all duration-300 disabled:opacity-50 shadow-lg shadow-emerald-500/20">
                                {isLoading ? '⏳ Вхожу...' : '✉️ Войти по Email'}
                            </button>
                            <p className="text-neutral-600 text-xs text-center">Нет аккаунта? <button type="button" onClick={() => setActiveTab('register')} className="text-emerald-400 underline">Зарегистрируйтесь</button></p>
                        </motion.form>
                    )}

                    {activeTab === 'register' && (
                        <motion.form key="register" initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -10 }}
                            onSubmit={handleRegister} className="space-y-4">
                            <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl">
                                <p className="text-amber-400 text-xs text-center">🎁 При регистрации — <strong>3 дня PRO бесплатно!</strong></p>
                            </div>
                            <div>
                                <label className="block text-neutral-400 text-xs font-medium mb-1.5 uppercase tracking-wider">Ваше имя</label>
                                <input type="text" value={name} onChange={e => setName(e.target.value)}
                                    placeholder="Как вас зовут?" required
                                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-neutral-600 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 transition-all" />
                            </div>
                            <div>
                                <label className="block text-neutral-400 text-xs font-medium mb-1.5 uppercase tracking-wider">Email</label>
                                <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                                    placeholder="your@email.com" required
                                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-neutral-600 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 transition-all" />
                            </div>
                            <div>
                                <label className="block text-neutral-400 text-xs font-medium mb-1.5 uppercase tracking-wider">Пароль</label>
                                <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                                    placeholder="Минимум 6 символов" required
                                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-neutral-600 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 transition-all" />
                            </div>
                            <div>
                                <label className="block text-neutral-400 text-xs font-medium mb-1.5 uppercase tracking-wider">Повторите пароль</label>
                                <input type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)}
                                    placeholder="Повторите пароль" required
                                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-neutral-600 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 transition-all" />
                            </div>
                            <button type="submit" disabled={isLoading}
                                className="w-full py-3.5 bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-white font-bold rounded-xl transition-all duration-300 disabled:opacity-50 shadow-lg shadow-amber-500/20">
                                {isLoading ? '⏳ Создаю аккаунт...' : '🚀 Зарегистрироваться'}
                            </button>
                        </motion.form>
                    )}

                    {activeTab === 'telegram' && (
                        <motion.form key="telegram" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                            onSubmit={handleTelegramSubmit} className="space-y-4">
                            <div>
                                <label className="block text-neutral-400 text-xs font-medium mb-1.5 uppercase tracking-wider">Ваш Telegram ID</label>
                                <input type="text" inputMode="numeric" pattern="[0-9]*" value={telegramId} onChange={e => setTelegramId(e.target.value)}
                                    placeholder="Например: 432823154" required
                                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-neutral-600 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 transition-all" />
                                <p className="text-neutral-600 text-[10px] mt-1">Узнать свой ID — бот @userinfobot</p>
                            </div>
                            <div>
                                <label className="block text-neutral-400 text-xs font-medium mb-1.5 uppercase tracking-wider">Пароль проекта</label>
                                <input type="password" value={tgPassword} onChange={e => setTgPassword(e.target.value)}
                                    placeholder="Пароль от куратора" required
                                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-neutral-600 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 transition-all" />
                            </div>
                            <button type="submit" disabled={isLoading}
                                className="w-full py-3.5 bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-500 hover:to-green-500 text-white font-bold rounded-xl transition-all duration-300 disabled:opacity-50 shadow-lg shadow-emerald-500/20">
                                {isLoading ? '⏳ Вхожу...' : '🤖 Войти'}
                            </button>
                            <div className="mt-4 p-3 bg-white/[0.02] border border-white/5 rounded-xl">
                                <p className="text-neutral-500 text-xs text-center leading-relaxed">
                                    💡 Напишите боту <code className="text-emerald-400/80">/web</code> — он выдаст прямую ссылку для входа без пароля.
                                </p>
                            </div>
                        </motion.form>
                    )}
                </AnimatePresence>
            </motion.div>
        </div>
    );
}
