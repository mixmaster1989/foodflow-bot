import React, { useState, useRef, useEffect } from 'react'
import { X, Mic, Send, Loader2, Camera, Scale, CheckCircle2, Star, Leaf, AlertTriangle } from 'lucide-react'
import { universalApi, consumptionApi, savedDishesApi } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import { useToast } from './Toast'
import { useVoiceRecorder } from '../hooks/useVoiceRecorder'
import { SavedMealsModal } from './SavedMealsModal'

interface QuickLogModalProps {
    isOpen: boolean
    onClose: () => void
    onSuccess: () => void
}

export function QuickLogModal({ isOpen, onClose, onSuccess }: QuickLogModalProps) {
    const { isPro, isBasic } = useAuth()
    const toast = useToast()
    const [text, setText] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [stage, setStage] = useState<'input' | 'clarify_weight' | 'confirm'>('input')
    const [pendingData, setPendingData] = useState<any>(null)
    const [timeOption, setTimeOption] = useState<'now' | '-1h' | '-2h'>('now')
    const [isSavedMealsOpen, setIsSavedMealsOpen] = useState(false)
    const [showSuccess, setShowSuccess] = useState(false)
    const inputRef = useRef<HTMLInputElement>(null)
    const photoInputRef = useRef<HTMLInputElement>(null)
    const { isRecording, startRecording, stopRecording } = useVoiceRecorder()

    useEffect(() => {
        if (isOpen && inputRef.current && stage === 'input') {
            setTimeout(() => inputRef.current?.focus(), 100)
        }
        if (!isOpen) {
            setText('')
            setStage('input')
            setPendingData(null)
            setIsLoading(false)
            setTimeOption('now')
            setShowSuccess(false)
        }
    }, [isOpen, stage])

    const getTargetDate = () => {
        const now = new Date()
        if (timeOption === '-1h') now.setHours(now.getHours() - 1)
        if (timeOption === '-2h') now.setHours(now.getHours() - 2)
        return now.toISOString()
    }

    const handleAnalysisParsed = async (res: any) => {
        if (res.success && res.analysis) {
            const norm = res.analysis.normalization;
            if (res.analysis.type === 'herbalife') {
                const hProd = res.analysis.product;
                const hNutr = res.analysis.nutrition;
                setPendingData({
                    type: 'herbalife',
                    product_name: hProd.name,
                    calories: hNutr.calories,
                    protein: hNutr.protein,
                    fat: hNutr.fat,
                    carbs: hNutr.carbs,
                    fiber: hNutr.fiber,
                    warnings: hNutr.warnings || [],
                    weight_g: hNutr.weight,
                    unit: hNutr.unit || 'ложки'
                });
                setStage('confirm');
                setText('');
            } else if (norm) {
                if (norm.weight_missing) {
                    setPendingData(norm);
                    setStage('clarify_weight');
                    setText('');
                } else {
                    setPendingData(norm);
                    setStage('confirm');
                    setText('');
                }
            } else {
                toast.error(res.message || 'Не удалось распознать еду');
            }
        } else {
            toast.error(res.message || 'Ошибка анализа');
        }
    };

    const handleConfirmSave = async () => {
        setIsLoading(true);
        try {
            if (pendingData.type === 'herbalife') {
                await consumptionApi.manualLog({
                    product_name: pendingData.product_name,
                    calories: pendingData.calories,
                    protein: pendingData.protein,
                    fat: pendingData.fat,
                    carbs: pendingData.carbs,
                    fiber: pendingData.fiber,
                    weight_g: undefined,
                    date: getTargetDate()
                });
            } else {
                await consumptionApi.manualLog({
                    product_name: pendingData.product_name || pendingData.base_name || pendingData.name,
                    calories: pendingData.calories,
                    protein: pendingData.protein,
                    fat: pendingData.fat,
                    carbs: pendingData.carbs,
                    fiber: pendingData.fiber || 0,
                    weight_g: pendingData.weight_grams,
                    date: getTargetDate()
                });
            }
            setShowSuccess(true);
            // Trigger AI Whisper
            window.dispatchEvent(new CustomEvent('ff-whisper', {
                detail: {
                    action: 'food_log',
                    detail: pendingData.product_name || pendingData.base_name || pendingData.name
                }
            }));
            onSuccess();
            setTimeout(() => {
                onClose();
            }, 1000);
        } catch (err) {
            console.error(err);
            toast.error('Ошибка сохранения');
        } finally {
            setIsLoading(false);
        }
    };

    const handleVoiceToggle = async () => {
        if (!isBasic) {
            toast.info('Голосовой ввод доступен в тарифе Basic и выше');
            return;
        }

        if (isRecording) {
            setIsLoading(true);
            try {
                const audioBlob = await stopRecording();
                if (audioBlob.size < 100) throw new Error('Запись слишком короткая');

                const res = await universalApi.process({ file: audioBlob });
                handleAnalysisParsed(res);
            } catch (err) {
                console.error(err);
                toast.error('Ошибка записи голоса');
            } finally {
                setIsLoading(false);
            }
        } else {
            await startRecording();
        }
    };

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        if (!isPro) {
            toast.info('Анализ фото доступен в тарифе PRO');
            if (photoInputRef.current) photoInputRef.current.value = '';
            return;
        }

        setIsLoading(true);
        try {
            const res = await universalApi.process({ file });
            handleAnalysisParsed(res);
        } catch (err) {
            console.error(err);
            toast.error('Ошибка обработки файла');
        } finally {
            setIsLoading(false);
            if (photoInputRef.current) photoInputRef.current.value = '';
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!text.trim()) return

        setIsLoading(true)
        try {
            if (stage === 'input') {
                const res = await universalApi.process({ text: text })
                await handleAnalysisParsed(res)
            } else if (stage === 'clarify_weight') {
                const weight = parseFloat(text.replace(',', '.'))
                if (isNaN(weight) || weight <= 0) {
                    toast.error('Введите корректный вес')
                    setIsLoading(false)
                    return
                }

                setPendingData({ ...pendingData, weight_grams: weight });
                setStage('confirm');
                setText('');
            }
        } catch (err) {
            console.error(err)
            toast.error('Ошибка при сохранении')
        } finally {
            setIsLoading(false)
        }
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center p-4 sm:p-0">
            <div
                className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
                onClick={onClose}
            ></div>

            <div className="relative w-full max-w-md bg-neutral-900 border border-neutral-800 rounded-3xl p-6 shadow-2xl transform transition-all animate-in fade-in slide-in-from-bottom-4">
                <button
                    onClick={onClose}
                    className="absolute right-4 top-4 text-neutral-500 hover:text-white transition-colors"
                >
                    <X className="w-6 h-6" />
                </button>

                <div className="mb-6">
                    <h2 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-indigo-500 bg-clip-text text-transparent flex items-center gap-2">
                        {stage === 'input' ? '⚡ Быстрая запись' : stage === 'clarify_weight' ? '⚖️ Уточните вес' : 'Подтвердите запись'}
                    </h2>
                    <p className="text-neutral-400 text-sm mt-1">
                        {stage === 'input'
                            ? 'Например: "Яблоко 150г" или просто "Яблоко"'
                            : stage === 'clarify_weight'
                                ? `Я понял, это ${pendingData?.base_name || pendingData?.name}. Сколько грамм?`
                                : 'Проверьте данные и подтвердите запись'
                        }
                    </p>
                </div>

                {showSuccess ? (
                    <div className="flex flex-col items-center justify-center py-12 animate-in zoom-in duration-300">
                        <div className="w-20 h-20 bg-emerald-500/10 rounded-full flex items-center justify-center mb-4">
                            <CheckCircle2 className="w-12 h-12 text-emerald-500" />
                        </div>
                        <h3 className="text-xl font-bold text-white mb-2">Успешно!</h3>
                        <p className="text-neutral-400 text-center">Ваша запись сохранена в дневник.</p>
                    </div>
                ) : (
                    <>
                        {stage === 'input' && (
                            <div className="flex bg-neutral-900 border border-neutral-800 rounded-xl p-1 mb-4">
                                <button
                                    type="button"
                                    onClick={() => setTimeOption('now')}
                                    className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-colors ${timeOption === 'now' ? 'bg-neutral-800 text-white shadow-sm' : 'text-neutral-500 hover:text-neutral-300'}`}
                                >
                                    Сейчас
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setTimeOption('-1h')}
                                    className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-colors ${timeOption === '-1h' ? 'bg-neutral-800 text-white shadow-sm' : 'text-neutral-500 hover:text-neutral-300'}`}
                                >
                                    Час назад
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setTimeOption('-2h')}
                                    className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-colors ${timeOption === '-2h' ? 'bg-neutral-800 text-white shadow-sm' : 'text-neutral-500 hover:text-neutral-300'}`}
                                >
                                    Два часа назад
                                </button>
                            </div>
                        )}

                        {stage === 'confirm' && pendingData ? (
                            <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-300 mb-4">
                                <div className="bg-neutral-800/50 border border-neutral-700 p-4 rounded-xl">
                                    <div className="mb-4">
                                        <label className="block text-[10px] text-neutral-500 uppercase tracking-widest mb-1 ml-1 text-left">Название</label>
                                        <input
                                            value={pendingData.product_name || pendingData.name || pendingData.base_name}
                                            onChange={(e) => setPendingData({ ...pendingData, product_name: e.target.value, name: e.target.value })}
                                            className={`w-full bg-neutral-900 border ${pendingData.type === 'herbalife' ? 'border-emerald-500/50' : 'border-neutral-800'} rounded-lg px-3 py-2 ${pendingData.type === 'herbalife' ? 'text-emerald-400' : 'text-emerald-400'} font-bold focus:outline-none focus:border-emerald-500 transition-all`}
                                        />
                                    </div>

                                    {pendingData.type === 'herbalife' && (
                                        <div className="mb-4 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl animate-in zoom-in duration-300">
                                            <div className="flex items-center gap-2 text-emerald-400 font-black text-[10px] tracking-widest uppercase mb-2">
                                                <Leaf className="w-3 h-3" /> ЭКСПЕРТНЫЙ РАЗБОР ГЕРБАЛАЙФ
                                            </div>
                                            <p className="text-xs text-neutral-300 leading-relaxed italic">
                                                Данные взяты из базы эксперта. Дозировка: <b>{pendingData.weight_g} {pendingData.unit}</b>.
                                            </p>

                                            {pendingData.warnings && pendingData.warnings.length > 0 && (
                                                <div className="mt-3 space-y-1">
                                                    {pendingData.warnings.map((w: string, i: number) => (
                                                        <div key={i} className="flex items-start gap-2 text-[10px] text-amber-200 bg-amber-500/10 p-1.5 rounded-lg border border-amber-500/20">
                                                            <AlertTriangle className="w-3 h-3 flex-shrink-0 mt-0.5" />
                                                            <span>{w}</span>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    <div className="grid grid-cols-2 gap-3 mb-4">
                                        <div>
                                            <label className="block text-[10px] text-neutral-500 uppercase tracking-widest mb-1 ml-1 text-left">Вес (г)</label>
                                            <input
                                                type="number"
                                                value={pendingData.weight_grams || 0}
                                                onChange={(e) => setPendingData({ ...pendingData, weight_grams: parseFloat(e.target.value) || 0 })}
                                                className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-white font-medium focus:outline-none focus:border-emerald-500 transition-all"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-[10px] text-neutral-500 uppercase tracking-widest mb-1 ml-1 text-left">Калории</label>
                                            <input
                                                type="number"
                                                value={Math.round(pendingData.calories || 0)}
                                                onChange={(e) => setPendingData({ ...pendingData, calories: parseFloat(e.target.value) || 0 })}
                                                className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-white font-medium focus:outline-none focus:border-emerald-500 transition-all"
                                            />
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-4 gap-2">
                                        <div>
                                            <label className="block text-[10px] text-blue-500 font-bold mb-1">Б</label>
                                            <input
                                                type="number"
                                                step="0.1"
                                                value={(pendingData.protein || 0).toFixed(1)}
                                                onChange={(e) => setPendingData({ ...pendingData, protein: parseFloat(e.target.value) || 0 })}
                                                className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-1 py-1.5 text-center text-white text-xs focus:outline-none focus:border-blue-500"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-[10px] text-amber-500 font-bold mb-1">Ж</label>
                                            <input
                                                type="number"
                                                step="0.1"
                                                value={(pendingData.fat || 0).toFixed(1)}
                                                onChange={(e) => setPendingData({ ...pendingData, fat: parseFloat(e.target.value) || 0 })}
                                                className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-1 py-1.5 text-center text-white text-xs focus:outline-none focus:border-amber-500"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-[10px] text-purple-500 font-bold mb-1">У</label>
                                            <input
                                                type="number"
                                                step="0.1"
                                                value={(pendingData.carbs || 0).toFixed(1)}
                                                onChange={(e) => setPendingData({ ...pendingData, carbs: parseFloat(e.target.value) || 0 })}
                                                className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-1 py-1.5 text-center text-white text-xs focus:outline-none focus:border-purple-500"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-[10px] text-emerald-500 font-bold mb-1">Кл</label>
                                            <input
                                                type="number"
                                                step="0.1"
                                                value={(pendingData.fiber || 0).toFixed(1)}
                                                onChange={(e) => setPendingData({ ...pendingData, fiber: parseFloat(e.target.value) || 0 })}
                                                className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-1 py-1.5 text-center text-white text-xs focus:outline-none focus:border-emerald-500"
                                            />
                                        </div>
                                    </div>
                                </div>

                                <button
                                    onClick={async () => {
                                        try {
                                            await savedDishesApi.create({
                                                name: pendingData.product_name || pendingData.name || pendingData.base_name,
                                                dish_type: "dish",
                                                components: [{
                                                    name: pendingData.product_name || pendingData.name || pendingData.base_name,
                                                    calories: pendingData.calories || 0,
                                                    protein: pendingData.protein || 0,
                                                    fat: pendingData.fat || 0,
                                                    carbs: pendingData.carbs || 0,
                                                    fiber: pendingData.fiber || 0,
                                                    weight_g: pendingData.weight_grams
                                                }],
                                                total_calories: pendingData.calories || 0,
                                                total_protein: pendingData.protein || 0,
                                                total_fat: pendingData.fat || 0,
                                                total_carbs: pendingData.carbs || 0,
                                                total_fiber: pendingData.fiber || 0,
                                            });
                                            setShowSuccess(true);
                                            setTimeout(() => {
                                                setShowSuccess(false);
                                            }, 1500);
                                        } catch (e) { toast.error('Ошибка сохранения блюда'); }
                                    }}
                                    className="w-full flex items-center justify-center gap-2 bg-neutral-800/80 hover:bg-neutral-700 text-neutral-300 font-medium py-3 rounded-xl transition-colors mb-4 border border-neutral-700"
                                >
                                    <Star className="w-4 h-4 text-amber-500" />
                                    Сохранить блюдо
                                </button>
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => setStage('input')}
                                        className="flex-1 bg-neutral-800 hover:bg-neutral-700 text-white font-bold py-4 rounded-2xl transition-colors"
                                    >
                                        Отмена
                                    </button>
                                    <button
                                        onClick={handleConfirmSave}
                                        disabled={isLoading}
                                        className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-4 rounded-2xl transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                                    >
                                        {isLoading ? 'Сохранение...' : <><CheckCircle2 className="w-5 h-5" /> Записать</>}
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <form onSubmit={handleSubmit} className="relative">
                                <div className="relative">
                                    {stage === 'clarify_weight' && (
                                        <Scale className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-neutral-500" />
                                    )}
                                    <input
                                        ref={inputRef}
                                        value={text}
                                        onChange={(e) => setText(e.target.value)}
                                        placeholder={stage === 'input' ? "Что съели?" : "Вес в граммах..."}
                                        className={`w-full bg-neutral-800/50 border border-neutral-700 rounded-2xl pl-11 pr-11 py-4 text-lg focus:outline-none focus:border-blue-500 transition-all text-white placeholder:text-neutral-600`}
                                        disabled={isLoading}
                                        autoComplete="off"
                                        type={stage === 'clarify_weight' ? 'number' : 'text'}
                                    />

                                    {stage === 'input' && !text && (
                                        <>
                                            <input
                                                type="file"
                                                accept="image/*"
                                                capture="environment"
                                                className="hidden"
                                                ref={photoInputRef}
                                                onChange={handleFileUpload}
                                            />
                                            <button
                                                type="button"
                                                onClick={() => photoInputRef.current?.click()}
                                                className={`absolute left-3 top-1/2 -translate-y-1/2 p-2 transition-colors ${!isPro ? 'text-neutral-700' : 'text-neutral-500 hover:text-amber-400'}`}
                                            >
                                                <Camera className="w-5 h-5" />
                                                {!isPro && <div className="absolute -top-1 -right-1 text-[8px]">🔒</div>}
                                            </button>
                                            <button
                                                type="button"
                                                onClick={(e) => {
                                                    e.preventDefault();
                                                    e.stopPropagation();
                                                    console.log("Mic button clicked!");
                                                    handleVoiceToggle();
                                                }}
                                                className={`absolute right-3 top-1/2 -translate-y-1/2 p-2 transition-colors ${isRecording ? 'bg-red-500/10 text-red-500 animate-pulse rounded-full' : (!isBasic ? 'text-neutral-700' : 'text-neutral-500 hover:text-blue-400')}`}
                                            >
                                                <Mic className="w-5 h-5" />
                                                {!isBasic && !isRecording && <div className="absolute -top-1 -right-1 text-[8px]">🔒</div>}
                                            </button>
                                        </>
                                    )}

                                    {text && (
                                        <button
                                            type="submit"
                                            disabled={isLoading}
                                            className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl transition-colors disabled:opacity-50"
                                        >
                                            {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                                        </button>
                                    )}
                                </div>

                                {stage === 'input' && (
                                    <div className="mt-4 flex gap-2 overflow-x-auto pb-1 no-scrollbar text-xs">
                                        <button
                                            type="button"
                                            onClick={() => setIsSavedMealsOpen(true)}
                                            className="flex-shrink-0 px-3 py-1.5 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 rounded-full text-amber-400 transition-colors flex items-center gap-1 font-medium"
                                        >
                                            <Star className="w-3 h-3 fill-amber-400" /> Мои блюда
                                        </button>
                                        {['Кофе с молоком', 'Банан', 'Творог 5%', 'Яичница'].map(suggestion => (
                                            <button
                                                key={suggestion}
                                                type="button"
                                                onClick={() => setText(suggestion)}
                                                className="flex-shrink-0 px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 rounded-full text-neutral-300 transition-colors"
                                            >
                                                {suggestion}
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </form>
                        )}
                    </>
                )}
            </div>

            <SavedMealsModal
                isOpen={isSavedMealsOpen}
                onClose={() => setIsSavedMealsOpen(false)}
                onSuccess={onSuccess}
            />
        </div>
    )
}
