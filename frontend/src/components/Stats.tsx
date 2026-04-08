import React, { useState, useEffect } from 'react';
import { Home, Lock, BarChart2, ChevronLeft, ChevronRight, List } from 'lucide-react';
import { statsApi } from '../api/client';

interface StatsProps {
    onNavigate: (tab: any) => void;
    onOpenHistory: () => void;
}

import { useAuth } from '../hooks/useAuth';

export const Stats: React.FC<StatsProps> = ({ onNavigate, onOpenHistory }) => {
    const { isFree } = useAuth();

    const [currentDate, setCurrentDate] = useState<Date>(new Date());
    const [report, setReport] = useState<any>(null);
    const [isLoading, setIsLoading] = useState(false);

    const fetchStats = async (date: Date) => {
        setIsLoading(true);
        try {
            // YYYY-MM-DD local format
            const dateStr = date.toLocaleDateString('en-CA');
            const data = await statsApi.getDailyReport(dateStr);
            setReport(data);
        } catch (e) {
            console.error(e);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        if (!isFree) {
            fetchStats(currentDate);
        }
    }, [currentDate, isFree]);

    const changeDate = (days: number) => {
        const newDate = new Date(currentDate);
        newDate.setDate(newDate.getDate() + days);
        // Don't go into future
        if (newDate > new Date()) return;
        setCurrentDate(newDate);
    };

    const caloriesConsumed = report?.calories_consumed || 0;
    const caloriesGoal = report?.calories_goal || 2000;
    const caloriesPercent = Math.min(100, (caloriesConsumed / caloriesGoal) * 100);

    const macros = [
        { label: 'Белки', val: report?.protein || 0, goal: report?.protein_goal || 150, color: 'bg-blue-400', icon: '🥩' },
        { label: 'Жиры', val: report?.fat || 0, goal: report?.fat_goal || 70, color: 'bg-amber-400', icon: '🥑' },
        { label: 'Углеводы', val: report?.carbs || 0, goal: report?.carb_goal || 250, color: 'bg-purple-400', icon: '🥖' },
        { label: 'Клетчатка', val: report?.fiber || 0, goal: report?.fiber_goal || 25, color: 'bg-emerald-400', icon: '🥬' }
    ];

    return (
        <div className="pb-24 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center gap-2 mb-6 cursor-pointer" onClick={() => onNavigate('dashboard')}>
                <Home className="w-5 h-5 text-emerald-500" />
                <span className="text-emerald-500 font-medium text-sm">На главную</span>
            </div>

            <div className="flex justify-between items-center mb-6">
                <h2 className="font-semibold text-xl flex items-center gap-2 text-white">
                    <BarChart2 className="w-6 h-6 text-indigo-400" /> Статистика
                </h2>
            </div>

            {isFree ? (
                <div className="flex flex-col items-center justify-center p-8 bg-neutral-900/50 backdrop-blur-md border border-indigo-500/20 rounded-3xl text-center shadow-lg relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/10 blur-[60px] rounded-full pointer-events-none"></div>
                    <div className="w-20 h-20 bg-neutral-950 rounded-full flex items-center justify-center mb-4 border border-white/5 relative z-10">
                        <Lock className="w-10 h-10 text-neutral-500" />
                    </div>
                    <h3 className="text-xl font-bold text-white mb-2 relative z-10">Доступ закрыт</h3>
                    <p className="text-neutral-400 text-sm mb-6 relative z-10">
                        Подробная статистика за прошлые дни доступна только в PRO-версии.
                    </p>
                    <button
                        onClick={() => onNavigate('subscriptions')}
                        className="w-full max-w-[200px] bg-gradient-to-r from-indigo-500 to-purple-500 text-white font-bold py-3 px-6 rounded-2xl shadow-lg relative z-10 active:scale-95 transition-transform"
                    >
                        💎 Оформить PRO
                    </button>
                </div>
            ) : (
                <>
                    {/* Date Navigator */}
                    <div className="flex items-center justify-between bg-neutral-900 border border-neutral-800 rounded-2xl p-2 mb-6">
                        <button
                            onClick={() => changeDate(-1)}
                            className="p-3 text-neutral-400 hover:text-white bg-neutral-950 border border-white/5 rounded-xl transition-all active:scale-95"
                        >
                            <ChevronLeft className="w-5 h-5" />
                        </button>
                        <div className="text-center">
                            <span className="font-bold text-lg text-white block">
                                {currentDate.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })}
                            </span>
                            <span className="text-xs text-neutral-500 font-medium uppercase tracking-widest">
                                {currentDate.toLocaleDateString('en-CA') === new Date().toLocaleDateString('en-CA') ? 'Сегодня' :
                                    currentDate.toLocaleDateString('ru-RU', { weekday: 'long' })}
                            </span>
                        </div>
                        <button
                            onClick={() => changeDate(1)}
                            disabled={currentDate.toLocaleDateString('en-CA') === new Date().toLocaleDateString('en-CA')}
                            className="p-3 text-neutral-400 hover:text-white bg-neutral-950 border border-white/5 rounded-xl transition-all disabled:opacity-50 disabled:pointer-events-none active:scale-95"
                        >
                            <ChevronRight className="w-5 h-5" />
                        </button>
                    </div>

                    <div className={`transition-opacity duration-300 ${isLoading ? 'opacity-50' : 'opacity-100'}`}>
                        <section className="glass-panel border-indigo-500/20 rounded-3xl p-6 relative overflow-hidden group mb-4">
                            <div className="absolute top-0 right-0 w-40 h-40 bg-indigo-500/10 blur-[80px] rounded-full pointer-events-none"></div>

                            {/* Circular Progress */}
                            <div className="flex justify-center mb-8 relative mt-4">
                                <div className="relative w-48 h-48 flex items-center justify-center">
                                    <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                                        <circle cx="50" cy="50" r="45" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="8" />
                                        <circle cx="50" cy="50" r="45" fill="none" stroke="currentColor" strokeWidth="8"
                                            className="text-indigo-500 drop-shadow-[0_0_15px_rgba(99,102,241,0.5)] transition-all duration-1000 ease-out"
                                            strokeDasharray="283"
                                            strokeDashoffset={283 - (283 * caloriesPercent) / 100}
                                            strokeLinecap="round"
                                        />
                                    </svg>
                                    <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                                        <span className="text-4xl font-black bg-gradient-to-br from-white to-neutral-400 bg-clip-text text-transparent transform translate-y-2">
                                            {Math.round(caloriesConsumed)}
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
                                                <div
                                                    className={`absolute left-0 top-0 bottom-0 ${m.color} transition-all duration-1000 ease-out`}
                                                    style={{ width: `${pct}%`, boxShadow: `0 0 10px var(--tw-color-${m.color.split('-')[1]}-400)` }}
                                                ></div>
                                            </div>
                                            <span className="text-[10px] text-neutral-300 font-medium">{Math.round(m.val)}г</span>
                                        </div>
                                    );
                                })}
                            </div>
                        </section>

                        <button
                            onClick={onOpenHistory}
                            className="w-full glass-pill border border-neutral-800 bg-neutral-900 rounded-2xl p-4 flex items-center justify-center gap-3 transition-all hover:bg-neutral-800 active:scale-95"
                        >
                            <List className="w-5 h-5 text-indigo-400" />
                            <span className="font-semibold text-white">История записей за {currentDate.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })}</span>
                        </button>
                    </div>
                </>
            )}
        </div>
    );
};
