import React, { useState, useEffect } from 'react';
import { useToast } from '../components/Toast'
import { Home, Scale, TrendingDown, TrendingUp, Minus, Calendar, Plus, ChevronRight, History } from 'lucide-react';
import { weightApi } from '../api/client';

interface WeightProps {
    user: any;
    onNavigate: (tab: any) => void;
}

export const Weight: React.FC<WeightProps> = ({ user, onNavigate }) => {
    const toast = useToast()
    const [logs, setLogs] = useState<any[]>([]);
    const [weightInput, setWeightInput] = useState<string>('');
    const [isLoading, setIsLoading] = useState(false);
    const [showInput, setShowInput] = useState(false);

    const fetchLogs = async () => {
        try {
            const data = await weightApi.getLogs(30);
            setLogs(data);
        } catch (e) {
            console.error(e);
        }
    };

    useEffect(() => {
        fetchLogs();
    }, []);

    const handleLogWeight = async (e: React.FormEvent) => {
        e.preventDefault();
        const w = parseFloat(weightInput.replace(',', '.'));
        if (isNaN(w) || w <= 0 || w > 300) {
            toast.error('Введите корректный вес');
            return;
        }

        setIsLoading(true);
        try {
            await weightApi.logWeight(w);
            setWeightInput('');
            setShowInput(false);
            // Trigger AI Whisper
            window.dispatchEvent(new CustomEvent('ff-whisper', {
                detail: { action: 'weight_log', detail: `${w}kg` }
            }));
            fetchLogs();
        } catch (e) {
            toast.error('Ошибка при сохранении веса');
        } finally {
            setIsLoading(false);
        }
    };

    const currentWeight = logs.length > 0 ? logs[0].weight : (user?.weight || 0);
    const lastWeight = logs.length > 1 ? logs[1].weight : currentWeight;
    const diff = currentWeight - lastWeight;

    return (
        <div className="pb-24 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-lg mx-auto">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div
                    className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 rounded-full cursor-pointer hover:bg-emerald-500/20 transition-colors"
                    onClick={() => onNavigate('dashboard')}
                >
                    <Home className="w-4 h-4 text-emerald-500" />
                    <span className="text-emerald-500 font-medium text-xs">Главная</span>
                </div>
                <div className="px-3 py-1.5 bg-pink-500/10 rounded-full flex items-center gap-2">
                    <Scale className="w-4 h-4 text-pink-500" />
                    <span className="text-pink-500 font-bold text-xs uppercase tracking-wider">Вес Контроль</span>
                </div>
            </div>

            {/* Main Display Area */}
            <div className="relative mb-8">
                {/* Background Decoration */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-pink-500/10 blur-[80px] rounded-full -z-10 animate-pulse"></div>

                <div className="text-center space-y-2">
                    <p className="text-neutral-500 text-xs font-bold uppercase tracking-[0.2em]">Текущий показатель</p>
                    <div className="flex items-center justify-center gap-2">
                        <span className="text-7xl font-black text-white tracking-tighter tabular-nums drop-shadow-2xl">
                            {currentWeight ? currentWeight.toFixed(1) : '--'}
                        </span>
                        <span className="text-2xl text-neutral-600 font-bold mt-4">кг</span>
                    </div>

                    {logs.length > 1 && (
                        <div className={`inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-bold border transition-all duration-500 ${diff < 0
                            ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                            : diff > 0
                                ? 'bg-rose-500/10 border-rose-500/20 text-rose-400'
                                : 'bg-neutral-800 border-neutral-700 text-neutral-400'
                            }`}>
                            {diff < 0 ? <TrendingDown className="w-4 h-4" /> : diff > 0 ? <TrendingUp className="w-4 h-4" /> : <Minus className="w-4 h-4" />}
                            <span>{Math.abs(diff).toFixed(1)} кг</span>
                            <span className="text-[10px] opacity-60 font-medium ml-1 uppercase">с прошлого замера</span>
                        </div>
                    )}
                </div>
            </div>

            {/* Action Buttons */}
            {!showInput ? (
                <button
                    onClick={() => setShowInput(true)}
                    className="w-full relative group mb-10 overflow-hidden"
                >
                    <div className="absolute inset-0 bg-gradient-to-r from-pink-600 to-rose-600 transition-all group-hover:scale-105 active:scale-95 duration-500 rounded-3xl shadow-[0_10px_40px_-10px_rgba(225,29,72,0.4)]"></div>
                    <div className="relative flex items-center justify-center gap-3 py-5 text-white font-black text-lg">
                        <Plus className="w-6 h-6" />
                        ДОБАВИТЬ ЗАМЕР
                    </div>
                </button>
            ) : (
                <form
                    onSubmit={handleLogWeight}
                    className="relative mb-10 animate-in zoom-in duration-300"
                >
                    <div className="bg-neutral-900 border-2 border-pink-500/50 rounded-3xl p-2 shadow-2xl shadow-pink-500/20">
                        <div className="flex items-center">
                            <input
                                type="number"
                                step="0.1"
                                value={weightInput}
                                onChange={(e) => setWeightInput(e.target.value)}
                                placeholder="Введите новый вес..."
                                autoFocus
                                required
                                disabled={isLoading}
                                className="flex-1 bg-transparent px-6 py-4 text-2xl font-black text-white focus:outline-none placeholder:text-neutral-700 tabular-nums"
                            />
                            <div className="flex gap-2 pr-2">
                                <button
                                    type="button"
                                    onClick={() => setShowInput(false)}
                                    className="p-4 text-neutral-500 hover:text-white transition-colors font-bold text-sm"
                                >
                                    Отмена
                                </button>
                                <button
                                    type="submit"
                                    disabled={!weightInput || isLoading}
                                    className="px-8 py-4 bg-pink-600 hover:bg-pink-500 text-white font-black rounded-2xl transition-all shadow-lg active:scale-95"
                                >
                                    {isLoading ? '...' : 'OK'}
                                </button>
                            </div>
                        </div>
                    </div>
                </form>
            )}

            {/* History Section */}
            <div className="space-y-6">
                <div className="flex items-center justify-between px-2">
                    <h3 className="text-xs font-black text-neutral-500 uppercase tracking-[0.2em] flex items-center gap-2">
                        <History className="w-4 h-4" /> История взвешиваний
                    </h3>
                    {logs.length > 0 && (
                        <span className="text-[10px] text-neutral-600 font-bold uppercase">Последние {logs.length} записей</span>
                    )}
                </div>

                <div className="grid gap-3">
                    {logs.length > 0 ? (
                        logs.map((log: any, idx: number) => {
                            const prevWeight = idx < logs.length - 1 ? logs[idx + 1].weight : log.weight;
                            const stepDiff = log.weight - prevWeight;

                            return (
                                <div
                                    key={log.id}
                                    className="group relative bg-neutral-900/40 border border-white/5 rounded-3xl p-5 flex items-center justify-between transition-all hover:bg-neutral-800/60 hover:border-pink-500/20 hover:translate-y-[-2px]"
                                >
                                    <div className="flex items-center gap-4">
                                        <div className="w-12 h-12 bg-neutral-950 rounded-2xl flex items-center justify-center border border-white/5 transition-transform group-hover:scale-110">
                                            <Calendar className="w-5 h-5 text-neutral-600" />
                                        </div>
                                        <div>
                                            <div className="flex items-baseline gap-1">
                                                <span className="text-2xl font-black text-white tabular-nums tracking-tighter">
                                                    {log.weight.toFixed(1)}
                                                </span>
                                                <span className="text-xs text-neutral-600 font-bold">кг</span>
                                            </div>
                                            <p className="text-[10px] text-neutral-500 font-bold uppercase tracking-wider mt-0.5">
                                                {new Date(log.recorded_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })}
                                            </p>
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-3">
                                        {stepDiff !== 0 && (
                                            <div className={`flex flex-col items-end`}>
                                                <div className={`text-xs font-black flex items-center gap-1 ${stepDiff < 0 ? 'text-emerald-500' : 'text-rose-400'
                                                    }`}>
                                                    {stepDiff > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                                    {Math.abs(stepDiff).toFixed(1)}
                                                </div>
                                                <span className="text-[8px] text-neutral-600 font-black uppercase">изменено</span>
                                            </div>
                                        )}
                                        <ChevronRight className="w-4 h-4 text-neutral-800 group-hover:text-pink-500 transition-colors" />
                                    </div>
                                </div>
                            );
                        })
                    ) : (
                        <div className="py-20 flex flex-col items-center justify-center bg-neutral-900/30 border-2 border-dashed border-neutral-800 rounded-[40px] text-center px-10">
                            <div className="w-16 h-16 bg-neutral-950 rounded-3xl flex items-center justify-center mb-4 border border-white/5 opacity-50">
                                <Scale className="w-8 h-8 text-neutral-500" />
                            </div>
                            <h4 className="text-white font-bold mb-1">Замеров пока нет</h4>
                            <p className="text-neutral-500 text-sm">Начните историю своего преображения первым замерчиком!</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
