import React, { useEffect } from 'react';
import { Activity, Settings, Diamond, HelpCircle, MessageSquare, Layers } from 'lucide-react';
import { motion, useSpring, useTransform } from 'framer-motion';
import type { Variants } from 'framer-motion';

interface DashboardProps {
    user: any;
    report: any;
    onNavigate: (tab: any) => void;
    onOpenQuickLog: () => void;
    onOpenWater: () => void;
    onOpenHistory: () => void;
}

const AnimatedNumber: React.FC<{ value: number }> = ({ value }) => {
    const springValue = useSpring(0, { stiffness: 50, damping: 15 });
    const displayValue = useTransform(springValue, (latest) => Math.round(latest).toLocaleString());

    useEffect(() => {
        springValue.set(value);
    }, [value, springValue]);

    return <motion.span>{displayValue}</motion.span>;
};

import { useAuth } from '../hooks/useAuth';

export const Dashboard: React.FC<DashboardProps> = ({ user, report, onNavigate, onOpenQuickLog, onOpenWater, onOpenHistory }) => {
    const { isFree, isCurator, isAdmin } = useAuth();

    const caloriesConsumed = report?.calories_consumed || 0;
    const caloriesGoal = report?.calories_goal || 2000;
    const caloriesPercent = Math.min(100, (caloriesConsumed / caloriesGoal) * 100);
    const isFemale = user?.settings?.gender === 'female';

    const macros = [
        { label: 'Белки', val: report?.protein || 0, goal: report?.protein_goal || 150, color: 'bg-blue-400', icon: '🥩' },
        { label: 'Жиры', val: report?.fat || 0, goal: report?.fat_goal || 70, color: 'bg-amber-400', icon: '🥑' },
        { label: 'Углеводы', val: report?.carbs || 0, goal: report?.carb_goal || 250, color: 'bg-purple-400', icon: '🥖' },
        { label: 'Клетчатка', val: report?.fiber || 0, goal: report?.fiber_goal || 25, color: 'bg-emerald-400', icon: '🥬' }
    ];

    const containerVariants: Variants = {
        hidden: { opacity: 0 },
        visible: {
            opacity: 1,
            transition: {
                staggerChildren: 0.1,
                delayChildren: 0.2
            }
        }
    };

    const itemVariants: Variants = {
        hidden: { opacity: 0, y: 20 },
        visible: {
            opacity: 1,
            y: 0,
            transition: { type: "spring", stiffness: 100, damping: 15 }
        }
    };

    return (
        <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            className="space-y-6 pb-24"
        >
            {/* Metrics Dasboard: Calories Ring & Macros */}
            <motion.section
                variants={itemVariants}
                onClick={onOpenHistory}
                className="glass-panel rounded-3xl p-6 relative overflow-hidden group cursor-pointer hover:bg-white/5 transition-all active:scale-[0.98]"
            >
                <div className="absolute top-0 right-0 w-40 h-40 bg-emerald-500/10 blur-[80px] rounded-full pointer-events-none"></div>
                <div className="flex justify-between items-center mb-6">
                    <h2 className="font-semibold text-lg flex items-center gap-2 text-white">
                        <Activity className="w-5 h-5 text-emerald-500" /> Прогресс за день
                    </h2>
                    <motion.span
                        initial={{ scale: 0.8, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        className="text-emerald-500 text-sm font-bold bg-emerald-500/10 px-3 py-1 rounded-full border border-emerald-500/20"
                    >
                        {Math.round(caloriesPercent)}%
                    </motion.span>
                </div>

                {/* Circular Progress (Framer Motion based) */}
                <div className="flex justify-center mb-8 relative">
                    <div className="relative w-48 h-48 flex items-center justify-center">
                        <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                            {/* Background track */}
                            <circle cx="50" cy="50" r="45" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="6" />
                            {/* Progress track */}
                            <motion.circle
                                cx="50" cy="50" r="45" fill="none" stroke="currentColor" strokeWidth="6"
                                className="text-emerald-500 drop-shadow-[0_0_15px_rgba(16,185,129,0.5)]"
                                strokeDasharray="283"
                                initial={{ strokeDashoffset: 283 }}
                                animate={{ strokeDashoffset: 283 - (283 * caloriesPercent) / 100 }}
                                transition={{ duration: 1.5, ease: "circOut" }}
                                strokeLinecap="round"
                            />
                        </svg>
                        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                            <span className="text-4xl font-black bg-gradient-to-br from-white to-neutral-400 bg-clip-text text-transparent transform translate-y-2">
                                <AnimatedNumber value={caloriesConsumed} />
                            </span>
                            <span className="text-xs text-neutral-500 font-medium uppercase tracking-widest mt-1">/ {Math.round(caloriesGoal)} ккал</span>
                        </div>
                    </div>
                </div>

                {/* Macros Bars */}
                <div className="grid grid-cols-4 gap-3">
                    {macros.map((m) => {
                        const pct = Math.min(100, (m.val / m.goal) * 100);
                        return (
                            <div key={m.label} className="bg-black/20 rounded-2xl p-3 border border-white/5 flex flex-col items-center">
                                <span className="text-lg mb-1">{m.icon}</span>
                                <span className="text-[9px] text-neutral-400 mb-2 uppercase tracking-wide font-semibold text-center leading-tight h-6 flex items-center">{m.label}</span>
                                <div className="w-full h-2 bg-neutral-800/80 rounded-full overflow-hidden mb-1 relative">
                                    <motion.div
                                        initial={{ width: 0 }}
                                        animate={{ width: `${pct}%` }}
                                        transition={{ duration: 1, ease: "easeOut", delay: 0.5 }}
                                        className={`absolute left-0 top-0 bottom-0 ${m.color}`}
                                        style={{
                                            boxShadow: `0 0 10px var(--tw-color-${m.color.split('-')[1]}-400)`
                                        }}
                                    ></motion.div>
                                </div>
                                <span className="text-[10px] text-neutral-300 font-medium">
                                    <AnimatedNumber value={m.val} />г
                                </span>
                            </div>
                        );
                    })}
                </div>
            </motion.section>

            {/* Primary Actions */}
            <motion.div variants={itemVariants} className="grid grid-cols-[3fr_1fr] gap-4">
                <button
                    onClick={onOpenQuickLog}
                    className="glass-button rounded-3xl py-6 flex flex-col items-center justify-center gap-2 group relative overflow-hidden"
                >
                    <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
                    <span className="text-4xl transform group-hover:scale-110 transition-transform duration-300">🍽️</span>
                    <span className="font-bold text-lg text-emerald-50 uppercase tracking-wide drop-shadow-md">
                        {isFemale ? 'Я СЪЕЛА!' : 'Я СЪЕЛ!'}
                    </span>
                </button>

                <button
                    onClick={onOpenWater}
                    className="glass-pill rounded-3xl py-6 flex flex-col items-center justify-center gap-2 hover:bg-blue-500/10 hover:border-blue-500/30 transition-all group"
                >
                    <span className="text-3xl transform group-hover:scale-110 transition-transform duration-300 drop-shadow-[0_0_15px_rgba(59,130,246,0.5)]">💧</span>
                    <span className="font-semibold text-xs text-blue-200 uppercase tracking-widest mt-1">Вода</span>
                </button>
            </motion.div>

            {/* Navigation Grid */}
            <motion.div variants={itemVariants}>
                <h3 className="px-2 text-sm font-semibold text-neutral-400 uppercase tracking-widest mt-8 mb-4">Инструменты</h3>
                <div className="grid grid-cols-2 gap-3">
                    {[
                        { icon: '🧊', label: 'Холодильник', tab: 'fridge', locked: isFree },
                        { icon: '👨‍🍳', label: 'Рецепты', tab: 'recipes', locked: isFree },
                        { icon: '📊', label: 'Статистика', tab: 'stats', locked: isFree },
                        { icon: '🌿', label: 'Каталог HL', tab: 'herbalife' },
                        { icon: '⚖️', label: 'Вес', tab: 'weight' }
                    ].map((item) => (
                        <button
                            key={item.label}
                            onClick={() => onNavigate(item.tab)}
                            className={`glass-pill rounded-2xl p-5 flex items-center gap-4 transition-all hover:bg-white/5 active:scale-95 ${item.locked ? 'opacity-60 relative' : ''}`}
                        >
                            <span className="text-2xl">{item.icon}</span>
                            <span className="font-medium text-neutral-200">{item.label}</span>
                            {item.locked && (
                                <div className="absolute right-4 text-neutral-500">🔒</div>
                            )}
                        </button>
                    ))}
                </div>
            </motion.div>

            {/* System Menu */}
            <motion.div variants={itemVariants}>
                <h3 className="px-2 text-sm font-semibold text-neutral-400 uppercase tracking-widest mt-8 mb-4">Системное</h3>
                <div className="space-y-2">
                    {[
                        { icon: <Settings className="w-5 h-5" />, label: '⚙️ Настройки', tab: 'settings' },
                        { icon: <Diamond className="w-5 h-5 text-blue-400" />, label: '💎 Подписки', tab: 'subscriptions' },
                        { icon: <MessageSquare className="w-5 h-5" />, label: '🎁 Рефералка', tab: 'referrals' },
                        { icon: <HelpCircle className="w-5 h-5" />, label: 'ℹ️ Справка', tab: 'help' },
                        { icon: <MessageSquare className="w-5 h-5" />, label: '📩 Написать разработчику', tab: 'contact' }
                    ].map((item) => (
                        <button
                            key={item.label}
                            onClick={() => onNavigate(item.tab)}
                            className="w-full glass-pill rounded-xl p-4 flex items-center gap-4 transition-all hover:bg-white/5"
                        >
                            <span className="text-neutral-400">{item.icon}</span>
                            <span className="font-medium text-neutral-200">{item.label}</span>
                        </button>
                    ))}

                    {/* Curator Panel */}
                    {isCurator && (
                        <button
                            onClick={() => onNavigate('curator')}
                            className="w-full mt-4 glass-pill border-amber-500/30 bg-amber-500/5 rounded-xl p-4 flex items-center gap-4 transition-all hover:bg-amber-500/10"
                        >
                            <Layers className="w-5 h-5 text-amber-500" />
                            <span className="font-medium text-amber-100">👨‍🏫 Кабинет Куратора</span>
                        </button>
                    )}

                    {/* Admin Panel */}
                    {isAdmin && (
                        <button
                            onClick={() => onNavigate('admin')}
                            className="w-full mt-2 glass-pill border-red-500/30 bg-red-500/5 rounded-xl p-4 flex items-center gap-4 transition-all hover:bg-red-500/10"
                        >
                            <Settings className="w-5 h-5 text-red-500" />
                            <span className="font-medium text-red-100">🛡️ Панель Администратора</span>
                        </button>
                    )}
                </div>
            </motion.div>
        </motion.div>
    );
};
