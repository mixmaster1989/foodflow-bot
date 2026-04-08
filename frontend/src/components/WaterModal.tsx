import React, { useState, useEffect } from 'react';
import { X, Droplets, Trash2, Plus } from 'lucide-react';
import { waterApi } from '../api/client';

interface WaterModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSuccess: () => void;
}

export const WaterModal: React.FC<WaterModalProps> = ({ isOpen, onClose, onSuccess }) => {
    const [logs, setLogs] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [customAmount, setCustomAmount] = useState('');

    const fetchWater = async () => {
        try {
            const data = await waterApi.getLogs();
            setLogs(data);
        } catch (e) {
            console.error(e);
        }
    };

    useEffect(() => {
        if (isOpen) {
            fetchWater();
        }
    }, [isOpen]);

    if (!isOpen) return null;

    const totalWater = logs.reduce((sum, log) => sum + log.amount_ml, 0);

    const handleAdd = async (amount: number) => {
        setIsLoading(true);
        try {
            await waterApi.logWater(amount);
            await fetchWater();
            // Trigger AI Whisper
            window.dispatchEvent(new CustomEvent('ff-whisper', {
                detail: { action: 'water_log', detail: `${amount}ml` }
            }));
            onSuccess();
        } catch (e) {
            alert('Ошибка добавления воды');
        } finally {
            setIsLoading(false);
        }
    };

    const handleDelete = async (id: number) => {
        setIsLoading(true);
        try {
            await waterApi.deleteWater(id);
            await fetchWater();
            onSuccess();
        } catch (e) {
            console.error(e);
        } finally {
            setIsLoading(false);
        }
    };

    const handleCustomAdd = (e: React.FormEvent) => {
        e.preventDefault();
        const amount = parseInt(customAmount);
        if (amount > 0) {
            handleAdd(amount);
            setCustomAmount('');
        }
    };

    return (
        <div className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center animate-in fade-in duration-300">
            <div className="absolute inset-0 bg-neutral-950/80 backdrop-blur-sm" onClick={onClose} />

            <div className="relative w-full sm:w-full sm:max-w-md bg-neutral-900 border border-neutral-800 sm:rounded-3xl rounded-t-3xl p-6 shadow-2xl animate-in slide-in-from-bottom-8">
                {/* Decorative background glow */}
                <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/10 blur-[60px] rounded-full pointer-events-none"></div>

                <button onClick={onClose} className="absolute top-4 right-4 p-2 text-neutral-500 hover:text-white transition-colors bg-neutral-800 rounded-full">
                    <X className="w-5 h-5" />
                </button>

                <div className="mb-6 flex items-center gap-3">
                    <div className="w-12 h-12 rounded-2xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
                        <Droplets className="w-6 h-6" />
                    </div>
                    <div>
                        <h2 className="text-xl font-bold text-white">Вода</h2>
                        <p className="text-sm text-neutral-400">Выпито за сегодня: <span className="text-blue-400 font-bold">{totalWater} мл</span></p>
                    </div>
                </div>

                {/* Quick Add Presets */}
                <div className="grid grid-cols-2 gap-3 mb-6">
                    {[
                        { ml: 200, label: 'Стакан', icon: '🥤' },
                        { ml: 250, label: 'Большой', icon: '🥛' },
                        { ml: 500, label: 'Бутылка', icon: '🍼' },
                        { ml: 1000, label: 'Литр', icon: '💧' },
                    ].map(preset => (
                        <button
                            key={preset.ml}
                            disabled={isLoading}
                            onClick={() => handleAdd(preset.ml)}
                            className="glass-pill flex items-center gap-3 p-4 rounded-2xl hover:bg-blue-500/10 hover:border-blue-500/30 transition-all group disabled:opacity-50"
                        >
                            <span className="text-2xl group-hover:scale-110 transition-transform">{preset.icon}</span>
                            <div className="text-left flex flex-col">
                                <span className="font-bold text-white">+{preset.ml}</span>
                                <span className="text-[10px] text-neutral-500 uppercase tracking-widest">{preset.label}</span>
                            </div>
                        </button>
                    ))}
                </div>

                {/* Custom Input */}
                <form onSubmit={handleCustomAdd} className="relative mb-8">
                    <input
                        type="number"
                        value={customAmount}
                        onChange={e => setCustomAmount(e.target.value)}
                        placeholder="Свой объем (мл)"
                        className="w-full bg-neutral-950 border border-neutral-800 rounded-2xl pl-4 pr-14 py-4 focus:outline-none focus:border-blue-500 transition-colors"
                    />
                    <button
                        type="submit"
                        disabled={!customAmount || isLoading}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-blue-500 text-white rounded-xl disabled:opacity-50"
                    >
                        <Plus className="w-5 h-5" />
                    </button>
                </form>

                {/* Today's Logs */}
                {logs.length > 0 && (
                    <div>
                        <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-widest mb-3">История за день</h3>
                        <div className="space-y-2 max-h-40 overflow-y-auto no-scrollbar">
                            {logs.map((log: any) => (
                                <div key={log.id} className="flex items-center justify-between p-3 bg-neutral-900/50 border border-white/5 rounded-xl">
                                    <div className="flex items-center gap-3">
                                        <Droplets className="w-4 h-4 text-blue-400" />
                                        <span className="font-medium text-sm">{log.amount_ml} мл</span>
                                        <span className="text-xs text-neutral-500">
                                            {new Date(log.date).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                                        </span>
                                    </div>
                                    <button
                                        onClick={() => handleDelete(log.id)}
                                        disabled={isLoading}
                                        className="p-2 text-neutral-500 hover:text-red-400 bg-neutral-800 rounded-lg transition-colors"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
