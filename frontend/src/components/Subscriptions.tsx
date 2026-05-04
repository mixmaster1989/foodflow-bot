import React from 'react';
import { Home, CheckCircle2, ShieldAlert, Check } from 'lucide-react';
interface SubscriptionsProps {
    user: any;
    onNavigate: (tab: any) => void;
}

export const Subscriptions: React.FC<SubscriptionsProps> = ({ user, onNavigate }) => {
    const tier = user?.tier || 'free';
    const sub = user?.subscription;
    const params = new URLSearchParams(window.location.search);
    const vkPlatform = params.get('vk_platform') ?? '';
    const isVkNativeApp = ['mobile_android', 'mobile_iphone'].includes(vkPlatform);
    const isVkWeb = !!params.get('vk_user_id') && !isVkNativeApp;

    const handleBuy = () => {
        window.open('https://t.me/FoodFlow2026bot', '_blank');
    };

    const logoTier = (tier === 'pro' || user?.role === 'admin' || user?.role === 'curator') ? 'pro' : tier === 'basic' ? 'basic' : 'free';
    const tierLabel = tier === 'curator' ? 'CURATOR' : tier === 'pro' ? 'PRO' : tier === 'basic' ? 'BASIC' : 'FREE';

    // VK native mobile (Android / iOS)
    // Rule 5.4.1: no payment, no redirects, no hints about payment anywhere
    if (isVkNativeApp) {
        return (
            <div className="pb-24 animate-in fade-in slide-in-from-bottom-4 duration-500 text-white">
                <div className="flex items-center gap-2 mb-6 cursor-pointer" onClick={() => onNavigate('dashboard')}>
                    <Home className="w-5 h-5 text-emerald-500" />
                    <span className="text-emerald-500 font-medium text-sm">На главную</span>
                </div>
                <div className="bg-gradient-to-br from-neutral-900 to-neutral-800/80 border border-emerald-500/20 rounded-3xl p-6 mb-6 shadow-xl">
                    <div className="flex items-center gap-4 mb-4">
                        <div className="w-16 h-16 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center overflow-hidden">
                            <img src={`logos/${logoTier}.png`} alt="Tier" className="w-full h-full object-cover" />
                        </div>
                        <div>
                            <p className="text-xs text-neutral-400 font-bold uppercase tracking-widest mb-1">Ваш текущий тариф</p>
                            <span className="text-3xl font-black">{tierLabel}</span>
                        </div>
                    </div>
                    {tier !== 'free' && sub?.expires_at ? (
                        <div className="flex items-start gap-2 text-sm text-emerald-400 bg-emerald-500/10 p-3 rounded-2xl border border-emerald-500/20">
                            <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
                            <span>Активна до <b>{new Date(sub.expires_at).toLocaleDateString('ru-RU')}</b>.</span>
                        </div>
                    ) : (
                        <div className="flex items-start gap-2 text-sm text-amber-500 bg-amber-500/10 p-3 rounded-2xl border border-amber-500/20">
                            <ShieldAlert className="w-5 h-5 flex-shrink-0" />
                            <span>У вас базовые возможности сервиса.</span>
                        </div>
                    )}
                </div>
                <div className="glass-panel rounded-3xl p-6 space-y-4">
                    <h3 className="text-sm font-bold text-neutral-300 uppercase tracking-widest">Возможности тарифов</h3>
                    <div className="space-y-2 text-sm text-neutral-400">
                        <p className="font-semibold text-blue-400 mb-2">Basic</p>
                        <div className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-500" /> Голосовой ввод</div>
                        <div className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-500" /> Умный Холодильник</div>
                        <div className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-500" /> Подробная Статистика</div>
                        <div className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-500" /> Пакетный ввод</div>
                    </div>
                    <div className="border-t border-white/5 pt-4 space-y-2 text-sm text-neutral-400">
                        <p className="font-semibold text-amber-400 mb-2">Pro</p>
                        <div className="flex items-center gap-2"><Check className="w-4 h-4 text-amber-500" /> Анализ еды по Фото</div>
                        <div className="flex items-center gap-2"><Check className="w-4 h-4 text-amber-500" /> AI Генератор рецептов</div>
                        <div className="flex items-center gap-2"><Check className="w-4 h-4 text-amber-500" /> Сканер чеков</div>
                        <div className="flex items-center gap-2"><Check className="w-4 h-4 text-amber-500" /> Нейро-Нутрициолог 24/7</div>
                    </div>
                </div>
                <p className="text-center text-[10px] text-neutral-500 mt-8 px-6">
                    support@foodflow.ru · <a href="/landing/privacy.html" className="underline">Политика конфиденциальности</a>
                </p>
            </div>
        );
    }

    // VK web (vk.ru / m.vk.ru) — same as mobile: show tier info only, no payment, no mentions
    if (isVkWeb) {
        return (
            <div className="pb-24 animate-in fade-in slide-in-from-bottom-4 duration-500 text-white">
                <div className="flex items-center gap-2 mb-6 cursor-pointer" onClick={() => onNavigate('dashboard')}>
                    <Home className="w-5 h-5 text-emerald-500" />
                    <span className="text-emerald-500 font-medium text-sm">На главную</span>
                </div>
                <div className="bg-gradient-to-br from-neutral-900 to-neutral-800/80 border border-emerald-500/20 rounded-3xl p-6 mb-6 shadow-xl">
                    <div className="flex items-center gap-4 mb-4">
                        <div className="w-16 h-16 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center overflow-hidden">
                            <img src={`logos/${logoTier}.png`} alt="Tier" className="w-full h-full object-cover" />
                        </div>
                        <div>
                            <p className="text-xs text-neutral-400 font-bold uppercase tracking-widest mb-1">Ваш текущий тариф</p>
                            <span className="text-3xl font-black">{tierLabel}</span>
                        </div>
                    </div>
                    {tier !== 'free' && sub?.expires_at ? (
                        <div className="flex items-start gap-2 text-sm text-emerald-400 bg-emerald-500/10 p-3 rounded-2xl border border-emerald-500/20">
                            <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
                            <span>Активна до <b>{new Date(sub.expires_at).toLocaleDateString('ru-RU')}</b>.</span>
                        </div>
                    ) : (
                        <div className="flex items-start gap-2 text-sm text-amber-500 bg-amber-500/10 p-3 rounded-2xl border border-amber-500/20">
                            <ShieldAlert className="w-5 h-5 flex-shrink-0" />
                            <span>У вас базовые возможности сервиса.</span>
                        </div>
                    )}
                </div>
                <div className="glass-panel rounded-3xl p-6 space-y-4">
                    <h3 className="text-sm font-bold text-neutral-300 uppercase tracking-widest">Возможности тарифов</h3>
                    <div className="space-y-2 text-sm text-neutral-400">
                        <p className="font-semibold text-blue-400 mb-2">Basic</p>
                        <div className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-500" /> Голосовой ввод</div>
                        <div className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-500" /> Умный Холодильник</div>
                        <div className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-500" /> Подробная Статистика</div>
                        <div className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-500" /> Пакетный ввод</div>
                    </div>
                    <div className="border-t border-white/5 pt-4 space-y-2 text-sm text-neutral-400">
                        <p className="font-semibold text-amber-400 mb-2">Pro</p>
                        <div className="flex items-center gap-2"><Check className="w-4 h-4 text-amber-500" /> Анализ еды по Фото</div>
                        <div className="flex items-center gap-2"><Check className="w-4 h-4 text-amber-500" /> AI Генератор рецептов</div>
                        <div className="flex items-center gap-2"><Check className="w-4 h-4 text-amber-500" /> Сканер чеков</div>
                        <div className="flex items-center gap-2"><Check className="w-4 h-4 text-amber-500" /> Нейро-Нутрициолог 24/7</div>
                    </div>
                </div>
                <p className="text-center text-[10px] text-neutral-500 mt-8 px-6">
                    support@foodflow.ru · <a href="/landing/privacy.html" className="underline">Политика конфиденциальности</a>
                </p>
            </div>
        );
    }

    // Non-VK (Telegram / browser) — full functionality with Telegram payment
    return (
        <div className="pb-24 animate-in fade-in slide-in-from-bottom-4 duration-500 text-white">
            <div className="flex items-center gap-2 mb-6 cursor-pointer" onClick={() => onNavigate('dashboard')}>
                <Home className="w-5 h-5 text-emerald-500" />
                <span className="text-emerald-500 font-medium text-sm">На главную</span>
            </div>
            <div className="bg-gradient-to-br from-neutral-900 to-neutral-800/80 border border-emerald-500/20 rounded-3xl p-6 relative overflow-hidden mb-8 shadow-xl">
                <div className="absolute -top-10 -right-10 w-40 h-40 bg-emerald-500/10 blur-[60px] rounded-full pointer-events-none"></div>
                <div className="flex items-center gap-4 mb-4">
                    <div className="w-16 h-16 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center overflow-hidden shadow-2xl">
                        <img src={`logos/${logoTier}.png`} alt="Current Logo" className="w-full h-full object-cover" />
                    </div>
                    <div>
                        <p className="text-xs text-neutral-400 font-bold uppercase tracking-widest mb-1">Ваш текущий тариф</p>
                        <span className="text-3xl font-black">{tierLabel}</span>
                    </div>
                </div>
                {tier !== 'free' && sub?.expires_at ? (
                    <div className="flex items-start gap-2 text-sm text-emerald-400 bg-emerald-500/10 p-3 rounded-2xl border border-emerald-500/20">
                        <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
                        <span>Активна до <b>{new Date(sub.expires_at).toLocaleDateString('ru-RU')}</b>.</span>
                    </div>
                ) : (
                    <div className="flex items-start gap-2 text-sm text-amber-500 bg-amber-500/10 p-3 rounded-2xl border border-amber-500/20">
                        <ShieldAlert className="w-5 h-5 flex-shrink-0" />
                        <span>У вас базовые возможности. Подключите тариф для доступа к AI.</span>
                    </div>
                )}
            </div>
            <div className="space-y-6">
                <div className={`glass-panel rounded-3xl p-6 relative overflow-hidden group ${tier === 'basic' ? 'border-emerald-500/50' : 'border-white/5'}`}>
                    <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/5 blur-[60px] rounded-full"></div>
                    <div className="flex justify-between items-start mb-4">
                        <div className="flex gap-4">
                            <div className="w-12 h-12 rounded-xl bg-white/5 border border-white/10 overflow-hidden flex-shrink-0">
                                <img src="logos/basic.png" alt="Basic" className="w-full h-full object-cover" />
                            </div>
                            <div>
                                <span className="text-[10px] font-bold text-blue-400 uppercase tracking-widest bg-blue-500/10 px-2 py-1 rounded-md">Популярный выбор</span>
                                <h3 className="text-xl font-bold mt-2">Basic (Комфорт)</h3>
                            </div>
                        </div>
                        <div className="text-right"><p className="text-xl font-black">199 руб.</p></div>
                    </div>
                    <ul className="space-y-2 mb-6 text-sm text-neutral-400">
                        <li className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-500" /> Голосовой ввод (Voice AI)</li>
                        <li className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-500" /> Умный Холодильник</li>
                        <li className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-500" /> Подробная Статистика</li>
                        <li className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-500" /> Пакетный ввод (Batch)</li>
                    </ul>
                    <button onClick={handleBuy} className="w-full py-3 bg-neutral-800 hover:bg-neutral-700 rounded-xl font-bold transition-all border border-white/5">
                        {tier === 'basic' ? 'Продлить подписку' : 'Выбрать Basic'}
                    </button>
                </div>
                <div className={`glass-panel rounded-3xl p-6 relative overflow-hidden group ${tier === 'pro' ? 'border-amber-500/50' : 'border-white/5'}`}>
                    <div className="absolute top-0 right-0 w-32 h-32 bg-amber-500/10 blur-[60px] rounded-full"></div>
                    <div className="flex justify-between items-start mb-4">
                        <div className="flex gap-4">
                            <div className="w-12 h-12 rounded-xl bg-white/5 border border-white/10 overflow-hidden flex-shrink-0">
                                <img src="logos/pro.png" alt="Pro" className="w-full h-full object-cover" />
                            </div>
                            <div>
                                <span className="text-[10px] font-bold text-amber-500 uppercase tracking-widest bg-amber-500/10 px-2 py-1 rounded-md">Максимальный AI</span>
                                <h3 className="text-xl font-bold mt-2">Pro (Максимум)</h3>
                            </div>
                        </div>
                        <div className="text-right"><p className="text-xl font-black">299 руб.</p></div>
                    </div>
                    <ul className="space-y-2 mb-6 text-sm text-neutral-400">
                        <li className="flex items-center gap-2 text-emerald-300 font-medium">Все функции Basic, плюс:</li>
                        <li className="flex items-center gap-2"><Check className="w-4 h-4 text-amber-500" /> Анализ еды по Фото</li>
                        <li className="flex items-center gap-2"><Check className="w-4 h-4 text-amber-500" /> AI Генератор рецептов</li>
                        <li className="flex items-center gap-2"><Check className="w-4 h-4 text-amber-500" /> Сканер чеков (Авто-холод)</li>
                        <li className="flex items-center gap-2"><Check className="w-4 h-4 text-amber-500" /> Нейро-Нутрициолог 24/7</li>
                    </ul>
                    <button onClick={handleBuy} className="w-full py-3 bg-gradient-to-r from-amber-600 to-orange-500 hover:from-amber-500 hover:to-orange-400 rounded-xl font-bold transition-all shadow-lg shadow-amber-500/20">
                        {tier === 'pro' ? 'Продлить подписку' : 'Выбрать Pro'}
                    </button>
                </div>
            </div>
            <p className="text-center text-[10px] text-neutral-500 mt-8 px-6 italic">
                Все подписки оформляются через официальный бот @FoodFlow2026bot в Telegram.
            </p>
        </div>
    );
};
