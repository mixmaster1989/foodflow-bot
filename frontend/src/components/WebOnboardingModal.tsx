import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { authApi } from '../api/client';

interface WebOnboardingModalProps {
    onComplete: () => void;
}

const GOALS = [
    { value: 'lose_weight', label: '📉 Похудеть', emoji: '📉' },
    { value: 'maintain', label: '⚖️ Поддержать вес', emoji: '⚖️' },
    { value: 'gain_muscle', label: '💪 Набрать мышцы', emoji: '💪' },
    { value: 'eat_healthy', label: '🥗 Питаться правильно', emoji: '🥗' },
];

export function WebOnboardingModal({ onComplete }: WebOnboardingModalProps) {
    const [step, setStep] = useState(1);
    const [goal, setGoal] = useState('');
    const [gender, setGender] = useState('');
    const [age, setAge] = useState('');
    const [height, setHeight] = useState('');
    const [weight, setWeight] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleComplete = async () => {
        setError(null);
        setIsLoading(true);
        try {
            const ageNum = parseInt(age);
            const heightNum = parseInt(height);
            const weightNum = parseFloat(weight);

            // Validation
            if (!goal || !gender) throw new Error('Пожалуйста, заполните все шаги');
            if (ageNum < 10 || ageNum > 120) throw new Error('Некорректный возраст');
            if (heightNum < 100 || heightNum > 250) throw new Error('Некорректный рост');
            if (weightNum < 20 || weightNum > 300) throw new Error('Некорректный вес');

            // Calculate rough calorie goal
            let bmr = 0;
            if (gender === 'male') {
                bmr = 88.36 + (13.4 * weightNum) + (4.8 * heightNum) - (5.7 * ageNum);
            } else {
                bmr = 447.6 + (9.2 * weightNum) + (3.1 * heightNum) - (4.3 * ageNum);
            }
            const calorieGoal = Math.round(
                goal === 'lose_weight' ? bmr * 0.8
                    : goal === 'gain_muscle' ? bmr * 1.15
                        : bmr
            );

            await authApi.updateSettings({
                goal,
                gender,
                age: ageNum,
                height: heightNum,
                weight: weightNum,
                calorie_goal: calorieGoal,
                is_initialized: true,
            });

            onComplete();
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message || 'Ошибка');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 bg-neutral-950 flex items-center justify-center p-6">
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
                className="w-full max-w-sm">
                {/* Progress */}
                <div className="flex gap-2 mb-8">
                    {[1, 2, 3].map(s => (
                        <div key={s} className={`h-1 flex-1 rounded-full transition-all duration-300 ${s <= step ? 'bg-emerald-500' : 'bg-white/10'}`} />
                    ))}
                </div>

                <AnimatePresence mode="wait">
                    {step === 1 && (
                        <motion.div key="step1" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                            <h2 className="text-2xl font-bold text-white mb-2">🎯 Ваша цель</h2>
                            <p className="text-neutral-400 text-sm mb-6">Выберите главную цель для точного расчёта питания</p>
                            <div className="space-y-3">
                                {GOALS.map(g => (
                                    <button key={g.value} onClick={() => setGoal(g.value)}
                                        className={`w-full p-4 rounded-2xl border text-left font-medium transition-all ${goal === g.value ? 'bg-emerald-600/20 border-emerald-500 text-white' : 'bg-white/5 border-white/10 text-neutral-300 hover:border-white/30'}`}>
                                        {g.label}
                                    </button>
                                ))}
                            </div>
                            <button onClick={() => goal && setStep(2)} disabled={!goal}
                                className="w-full mt-6 py-3.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl transition-all disabled:opacity-40">
                                Далее →
                            </button>
                        </motion.div>
                    )}

                    {step === 2 && (
                        <motion.div key="step2" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                            <h2 className="text-2xl font-bold text-white mb-2">👤 Ваш пол</h2>
                            <p className="text-neutral-400 text-sm mb-6">Нужно для корректного расчёта КБЖУ</p>
                            <div className="grid grid-cols-2 gap-3">
                                {[{ v: 'male', l: '👨 Мужской' }, { v: 'female', l: '👩 Женский' }].map(g => (
                                    <button key={g.v} onClick={() => setGender(g.v)}
                                        className={`p-5 rounded-2xl border font-semibold text-lg transition-all ${gender === g.v ? 'bg-emerald-600/20 border-emerald-500 text-white' : 'bg-white/5 border-white/10 text-neutral-300 hover:border-white/30'}`}>
                                        {g.l}
                                    </button>
                                ))}
                            </div>
                            <button onClick={() => gender && setStep(3)} disabled={!gender}
                                className="w-full mt-6 py-3.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl transition-all disabled:opacity-40">
                                Далее →
                            </button>
                            <button onClick={() => setStep(1)} className="w-full mt-2 py-2 text-neutral-500 text-sm">← Назад</button>
                        </motion.div>
                    )}

                    {step === 3 && (
                        <motion.div key="step3" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                            <h2 className="text-2xl font-bold text-white mb-2">📊 Параметры тела</h2>
                            <p className="text-neutral-400 text-sm mb-6">Для точного расчёта нормы калорий</p>
                            <div className="space-y-3">
                                {[
                                    { label: 'Возраст (лет)', value: age, set: setAge, placeholder: '25', type: 'number', min: '10', max: '120' },
                                    { label: 'Рост (см)', value: height, set: setHeight, placeholder: '175', type: 'number', min: '100', max: '250' },
                                    { label: 'Вес (кг)', value: weight, set: setWeight, placeholder: '70', type: 'number', min: '20', max: '300' },
                                ].map(field => (
                                    <div key={field.label}>
                                        <label className="block text-neutral-400 text-xs font-medium mb-1.5 uppercase tracking-wider">{field.label}</label>
                                        <input type={field.type} inputMode="numeric" value={field.value}
                                            onChange={e => field.set(e.target.value)} placeholder={field.placeholder}
                                            min={field.min} max={field.max}
                                            className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-neutral-600 focus:outline-none focus:border-emerald-500/50 transition-all" />
                                    </div>
                                ))}
                            </div>
                            {error && <p className="text-red-400 text-sm mt-3 text-center">{error}</p>}
                            <button onClick={handleComplete} disabled={isLoading || !age || !height || !weight}
                                className="w-full mt-6 py-3.5 bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-500 hover:to-green-500 text-white font-bold rounded-xl transition-all disabled:opacity-40 shadow-lg shadow-emerald-500/20">
                                {isLoading ? '⏳ Сохраняю...' : '🚀 Начать использовать FoodFlow!'}
                            </button>
                            <button onClick={() => setStep(2)} className="w-full mt-2 py-2 text-neutral-500 text-sm">← Назад</button>
                        </motion.div>
                    )}
                </AnimatePresence>
            </motion.div>
        </div>
    );
}
