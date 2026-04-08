import React, { useEffect, useState } from 'react';
import { Home, Gift, Users, WalletCards, Copy, CheckCircle2 } from 'lucide-react';
import WebAppConfig from '@twa-dev/sdk';
import { referralsApi } from '../api/client';

interface ReferralsProps {
    user: any;
    onNavigate: (tab: any) => void;
}

interface PendingReward {
    id: number;
    reward_type: string;
    days: number;
    source: string;
}

interface ReferralsState {
    loading: boolean;
    error: string | null;
    signup_count: number;
    paid_count: number;
    ref_paid_count: number;
    has_month_pro_bonus: boolean;
    pending_rewards: PendingReward[];
    active_basic_days: number;
    active_pro_days: number;
    active_curator_days: number;
    referral_link: string | null;
}

export const Referrals: React.FC<ReferralsProps> = ({ user, onNavigate }) => {
    const [state, setState] = useState<ReferralsState>({
        loading: true,
        error: null,
        signup_count: 0,
        paid_count: 0,
        ref_paid_count: 0,
        has_month_pro_bonus: false,
        pending_rewards: [],
        active_basic_days: 0,
        active_pro_days: 0,
        active_curator_days: 0,
        referral_link: null,
    });

    const [copySuccess, setCopySuccess] = useState(false);

    const loadData = async () => {
        try {
            setState((prev) => ({ ...prev, loading: true, error: null }));
            const data = await referralsApi.getMe();
            setState({
                loading: false,
                error: null,
                ...data,
            });
        } catch (err) {
            console.error('Referrals fetch error:', err);
            setState((prev) => ({ ...prev, loading: false, error: 'Не удалось загрузить данные рефералок' }));
        }
    };

    useEffect(() => {
        loadData();
    }, []);

    const handleCopyLink = async () => {
        try {
            let link = state.referral_link;
            if (!link) {
                const resp = await referralsApi.generateLink();
                link = resp.referral_link;
                await loadData();
            }
            await navigator.clipboard.writeText(
                `Забирай 3 дня PRO в FoodFlow по моей ссылке: ${link}`
            );
            setCopySuccess(true);
            setTimeout(() => setCopySuccess(false), 2000);
        } catch {
            alert('Не удалось скопировать ссылку. Скопируйте её вручную.');
        }
    };

    const handleShare = async () => {
        let link = state.referral_link;
        if (!link) {
            const resp = await referralsApi.generateLink();
            link = resp.referral_link;
            await loadData();
        }
        const text =
            `Присоединяйся к FoodFlow — бот считает калории, рецепты и холодильник за тебя.\n` +
            `По моей ссылке получишь 3 дня PRO:\n${link}`;

        // Try native share if available (in TWA it may be proxied)
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const nav: any = navigator;
        if (nav.share) {
            try {
                await nav.share({ text });
                return;
            } catch {
                // fallback to alert below
            }
        }

        alert(text);
    };

    const handleActivateReward = async (rewardId: number) => {
        try {
            await referralsApi.activateReward(rewardId);
            await loadData();
            // Attempt to close WebApp to let user see updated state in боте, если нужно
            if (WebAppConfig.initDataUnsafe?.user) {
                // noop: оставляем открытым, UX приятнее
            }
        } catch (err) {
            console.error('Activate reward error', err);
            alert('Не удалось активировать бонус. Проверьте лимит или попробуйте позже.');
        }
    };

    const tier = user?.tier || 'free';
    const progressPct = Math.min(100, (state.ref_paid_count / 10) * 100);

    return (
        <div className="pb-24 animate-in fade-in slide-in-from-bottom-4 duration-500 text-white">
            <div className="flex items-center gap-2 mb-6 cursor-pointer" onClick={() => onNavigate('dashboard')}>
                <Home className="w-5 h-5 text-emerald-500" />
                <span className="text-emerald-500 font-medium text-sm">На главную</span>
            </div>

            <div className="bg-gradient-to-br from-neutral-900 to-neutral-800/80 border border-emerald-500/20 rounded-3xl p-6 relative overflow-hidden mb-8 shadow-xl">
                <div className="absolute -top-10 -right-10 w-40 h-40 bg-emerald-500/10 blur-[60px] rounded-full pointer-events-none"></div>

                <div className="flex items-center gap-4 mb-4">
                    <div className="w-14 h-14 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center overflow-hidden shadow-2xl">
                        <Gift className="w-7 h-7 text-emerald-400" />
                    </div>
                    <div>
                        <p className="text-xs text-neutral-400 font-bold uppercase tracking-widest mb-1">
                            Реферальная программа
                        </p>
                        <span className="text-2xl font-black">
                            {tier === 'curator' ? 'Бонусы куратора' : 'Бонусы за друзей'}
                        </span>
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-3 text-sm mt-2">
                    <div className="bg-black/30 rounded-2xl p-3 border border-white/5 flex items-center gap-2">
                        <Users className="w-4 h-4 text-emerald-400" />
                        <div>
                            <p className="text-[11px] text-neutral-400 uppercase tracking-wide">Пришло по ссылкам</p>
                            <p className="text-lg font-bold">{state.signup_count}</p>
                        </div>
                    </div>
                    <div className="bg-black/30 rounded-2xl p-3 border border-white/5 flex items-center gap-2">
                        <WalletCards className="w-4 h-4 text-amber-400" />
                        <div>
                            <p className="text-[11px] text-neutral-400 uppercase tracking-wide">Стали платными</p>
                            <p className="text-lg font-bold">{state.paid_count}</p>
                        </div>
                    </div>
                </div>

                <div className="mt-4">
                    <p className="text-xs text-neutral-400 mb-1">
                        Прогресс до месяца PRO: <b>{Math.min(state.ref_paid_count, 10)}/10</b> платящих
                    </p>
                    <div className="w-full h-2 bg-neutral-800 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-gradient-to-r from-emerald-400 via-emerald-500 to-amber-400"
                            style={{ width: `${progressPct}%` }}
                        ></div>
                    </div>
                    <p className="text-[11px] text-neutral-500 mt-1">
                        {state.has_month_pro_bonus
                            ? 'Бонус 1 месяц PRO уже начислен (см. бонусы).'
                            : `Осталось ещё ${Math.max(0, 10 - state.ref_paid_count)} платящих.`}
                    </p>
                </div>
            </div>

            {/* Link block */}
            <div className="glass-panel rounded-3xl p-5 mb-6 border border-emerald-500/30">
                <div className="flex items-center justify-between mb-3">
                    <div>
                        <p className="text-xs text-neutral-400 uppercase tracking-widest mb-1">Твоя ссылка</p>
                        <p className="text-sm text-neutral-200">
                            Новый пользователь по ссылке получает <b>3 дня PRO</b>.
                        </p>
                    </div>
                </div>
                <div className="bg-black/40 rounded-2xl p-3 border border-white/5 text-[11px] text-neutral-300 break-all mb-3">
                    {state.referral_link ? state.referral_link : 'Ссылка ещё не создана. Нажми «Скопировать», чтобы получить её.'}
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={handleCopyLink}
                        className="flex-1 flex items-center justify-center gap-2 py-2 text-xs font-semibold rounded-xl bg-emerald-600 hover:bg-emerald-500 transition-colors"
                    >
                        {copySuccess ? <CheckCircle2 className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                        {copySuccess ? 'Скопировано' : 'Скопировать'}
                    </button>
                    <button
                        onClick={handleShare}
                        className="flex-1 py-2 text-xs font-semibold rounded-xl bg-neutral-800 hover:bg-neutral-700 border border-white/10 transition-colors"
                    >
                        Поделиться
                    </button>
                </div>
            </div>

            {/* Bonuses */}
            <div className="space-y-4">
                <div className="glass-panel rounded-3xl p-5">
                    <p className="text-xs text-neutral-400 uppercase tracking-widest mb-3">Ожидающие бонусы</p>
                    {state.pending_rewards.length === 0 ? (
                        <p className="text-sm text-neutral-500">У тебя пока нет неактивированных бонусов.</p>
                    ) : (
                        <div className="space-y-2">
                            {state.pending_rewards.map((r) => (
                                <div
                                    key={r.id}
                                    className="flex items-center justify-between text-sm bg-black/30 border border-white/5 rounded-2xl px-3 py-2"
                                >
                                    <div>
                                        <p className="font-medium">
                                            {r.reward_type === 'basic_days'
                                                ? `Basic +${r.days} дн.`
                                                : r.reward_type === 'pro_days'
                                                ? `Pro +${r.days} дн.`
                                                : r.reward_type === 'curator_days'
                                                ? `Curator +${r.days} дн.`
                                                : `${r.reward_type} +${r.days} дн.`}
                                        </p>
                                        <p className="text-[10px] text-neutral-500">{r.source}</p>
                                    </div>
                                    <button
                                        onClick={() => handleActivateReward(r.id)}
                                        className="text-[11px] px-3 py-1 rounded-full bg-emerald-600 hover:bg-emerald-500 font-semibold"
                                    >
                                        Активировать
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                <div className="glass-panel rounded-3xl p-5">
                    <p className="text-xs text-neutral-400 uppercase tracking-widest mb-3">Активированные бонусы (итог)</p>
                    <ul className="text-sm text-neutral-200 space-y-1">
                        <li>Basic: <b>{state.active_basic_days}</b> дн.</li>
                        <li>Pro: <b>{state.active_pro_days}</b> дн.</li>
                        <li>Curator: <b>{state.active_curator_days}</b> дн.</li>
                    </ul>
                </div>
            </div>
        </div>
    );
};

