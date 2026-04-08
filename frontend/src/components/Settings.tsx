import React, { useState } from 'react';
import { Home, Settings as SettingsIcon, Save, Loader2, AlertCircle } from 'lucide-react';
import { authApi } from '../api/client';

interface SettingsProps {
    user: any;
    onNavigate: (tab: any) => void;
}

export const Settings: React.FC<SettingsProps> = ({ user, onNavigate }) => {
    const [settings, setSettings] = useState({
        gender: user?.settings?.gender || '',
        calorie_goal: user?.settings?.calorie_goal || 2000,
        protein_goal: user?.settings?.protein_goal || 150,
        fat_goal: user?.settings?.fat_goal || 70,
        carb_goal: user?.settings?.carb_goal || 250,
        fiber_goal: user?.settings?.fiber_goal || 30,
        water_goal: user?.settings?.water_goal || 2000,
        allergies: user?.settings?.allergies || ''
    });

    const [isLoading, setIsLoading] = useState(false);
    const [success, setSuccess] = useState(false);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { name, value } = e.target;
        setSettings(prev => ({
            ...prev,
            [name]: name.includes('goal') ? Number(value) : value
        }));
        setSuccess(false);
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        try {
            await authApi.updateSettings(settings);
            setSuccess(true);
            // We could use a context or callback to update the global `user` state,
            // but reloading the app on next mount will also work, or just showing success.
        } catch (err) {
            console.error(err);
            alert('Ошибка при сохранении настроек');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="pb-24 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center gap-2 mb-6 cursor-pointer" onClick={() => onNavigate('dashboard')}>
                <Home className="w-5 h-5 text-emerald-500" />
                <span className="text-emerald-500 font-medium text-sm">На главную</span>
            </div>

            <div className="flex justify-between items-center mb-6">
                <h2 className="font-semibold text-xl flex items-center gap-2 text-white">
                    <SettingsIcon className="w-6 h-6 text-neutral-400" /> Настройки
                </h2>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
                {/* Personal Settings */}
                <section className="bg-neutral-900/40 border border-white/5 rounded-3xl p-5">
                    <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-widest mb-4">Личные данные</h3>

                    <div className="space-y-4">
                        <div>
                            <label className="block text-xs font-semibold text-neutral-400 mb-1">Пол</label>
                            <select
                                name="gender"
                                value={settings.gender}
                                onChange={handleChange}
                                className="w-full bg-neutral-950 border border-neutral-800 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-emerald-500 transition-colors"
                            >
                                <option value="">Не указан</option>
                                <option value="male">Мужской</option>
                                <option value="female">Женский</option>
                            </select>
                        </div>

                        <div>
                            <label className="block text-xs font-semibold text-neutral-400 mb-1">Аллергии / Исключения</label>
                            <input
                                type="text"
                                name="allergies"
                                value={settings.allergies}
                                onChange={handleChange}
                                placeholder="Например: орехи, лактоза"
                                className="w-full bg-neutral-950 border border-neutral-800 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-emerald-500 transition-colors"
                            />
                            <p className="text-[10px] text-neutral-500 mt-1 flex items-center gap-1">
                                <AlertCircle className="w-3 h-3" /> Учитывается при ИИ-анализе продуктов
                            </p>
                        </div>
                    </div>
                </section>

                {/* Macros Goals */}
                <section className="bg-neutral-900/40 border border-white/5 rounded-3xl p-5 relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 blur-[40px] rounded-full pointer-events-none"></div>
                    <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-widest mb-4 relative z-10">Цели БЖУК</h3>

                    <div className="grid grid-cols-2 gap-4 relative z-10">
                        <div>
                            <label className="block text-xs font-semibold text-neutral-400 mb-1">Калории (ккал)</label>
                            <input type="number" name="calorie_goal" value={settings.calorie_goal} onChange={handleChange} className="w-full bg-neutral-950 border border-neutral-800 rounded-xl px-4 py-3 text-white font-bold" />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-neutral-400 mb-1">Вода (мл)</label>
                            <input type="number" name="water_goal" value={settings.water_goal} onChange={handleChange} className="w-full bg-neutral-950 border border-neutral-800 rounded-xl px-4 py-3 text-blue-400 font-bold" />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-neutral-400 mb-1">Белки (г)</label>
                            <input type="number" name="protein_goal" value={settings.protein_goal} onChange={handleChange} className="w-full bg-neutral-950 border border-neutral-800 rounded-xl px-4 py-3 text-blue-400 font-bold" />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-neutral-400 mb-1">Жиры (г)</label>
                            <input type="number" name="fat_goal" value={settings.fat_goal} onChange={handleChange} className="w-full bg-neutral-950 border border-neutral-800 rounded-xl px-4 py-3 text-amber-400 font-bold" />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-neutral-400 mb-1">Углеводы (г)</label>
                            <input type="number" name="carb_goal" value={settings.carb_goal} onChange={handleChange} className="w-full bg-neutral-950 border border-neutral-800 rounded-xl px-4 py-3 text-purple-400 font-bold" />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-neutral-400 mb-1">Клетчатка (г)</label>
                            <input type="number" name="fiber_goal" value={settings.fiber_goal} onChange={handleChange} className="w-full bg-neutral-950 border border-neutral-800 rounded-xl px-4 py-3 text-emerald-400 font-bold" />
                        </div>
                    </div>
                </section>

                <button
                    type="submit"
                    disabled={isLoading}
                    className={`w-full py-4 rounded-2xl font-bold flex items-center justify-center gap-2 transition-all ${success
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50'
                            : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-500/20'
                        }`}
                >
                    {isLoading ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                    ) : success ? (
                        <>Сохранено ✅</>
                    ) : (
                        <><Save className="w-5 h-5" /> Сохранить настройки</>
                    )}
                </button>
            </form>
        </div>
    );
};
