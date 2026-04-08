import re

with open('frontend/src/components/QuickLogModal.tsx', 'w') as f:
    f.write('''import React, { useState, useRef, useEffect } from 'react'
import { X, Mic, Send, Loader2, Camera, Scale, CheckCircle2 } from 'lucide-react'
import { universalApi } from '../../../api/routers/universal'
import { consumptionApi } from '../../../api/routers/consumption'
import { useVoiceRecorder } from '../hooks/useVoiceRecorder'
import { processBackendLog } from '../App'

interface QuickLogModalProps {
    user: any
    isOpen: boolean
    onClose: () => void
    onSuccess: () => void
}

export function QuickLogModal({ user, isOpen, onClose, onSuccess }: QuickLogModalProps) {
    const [text, setText] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [stage, setStage] = useState<'input' | 'clarify_weight' | 'confirm'>('input')
    const [pendingData, setPendingData] = useState<any>(null)
    const [timeOption, setTimeOption] = useState<'now' | '-1h' | '-2h'>('now')
    const inputRef = useRef<HTMLInputElement>(null)
    const photoInputRef = useRef<HTMLInputElement>(null)
    const { isRecording, startRecording, stopRecording } = useVoiceRecorder()

    const isPro = user?.tier === 'pro'
    const isBasic = user?.tier === 'basic' || isPro

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
                    weight_g: undefined
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
                alert(res.message || 'Не удалось распознать еду');
            }
        } else {
            alert(res.message || 'Ошибка анализа');
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
                await processBackendLog(pendingData, pendingData.weight_grams);
            }
            onSuccess();
            onClose();
        } catch (err) {
            console.error(err);
            alert("Ошибка сохранения");
        } finally {
            setIsLoading(false);
        }
    };

    const handleVoiceToggle = async () => {
        if (!isBasic) {
            alert('🎙 Голосовой ввод доступен только в тарифе Basic и выше!');
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
                alert('Ошибка записи голоса: ' + (err instanceof Error ? err.message : String(err)));
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
            alert('📸 Анализ фото и чеков доступен только в тарифе PRO! 💎');
            if (photoInputRef.current) photoInputRef.current.value = '';
            return;
        }

        setIsLoading(true);
        try {
            const res = await universalApi.process({ file });
            handleAnalysisParsed(res);
        } catch (err) {
            console.error(err);
            alert('Ошибка обработки файла');
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
                    alert('Введите корректный вес')
                    setIsLoading(false)
                    return
                }

                setPendingData({ ...pendingData, weight_grams: weight });
                setStage('confirm');
                setText('');
            }
        } catch (err) {
            console.error(err)
            alert('Ошибка при сохранении')
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
                        <div className="bg-neutral-800/50 border border-neutral-700 p-4 rounded-xl text-center">
                            <h3 className="text-emerald-400 font-bold text-lg mb-1">{pendingData.product_name || pendingData.name || pendingData.base_name}</h3>
                            {pendingData.weight_grams && <p className="text-neutral-400 text-sm mb-3">{pendingData.weight_grams} г</p>}
                            <div className="grid grid-cols-4 gap-2">
                                <div className="bg-neutral-900 rounded-lg p-2">
                                    <span className="block text-[10px] text-emerald-500 font-bold">Ккал</span>
                                    <span className="text-white font-medium text-sm">{Math.round(pendingData.calories || 0)}</span>
                                </div>
                                <div className="bg-neutral-900 rounded-lg p-2">
                                    <span className="block text-[10px] text-blue-500 font-bold">Белки</span>
                                    <span className="text-white font-medium text-sm">{(pendingData.protein || 0).toFixed(1)}</span>
                                </div>
                                <div className="bg-neutral-900 rounded-lg p-2">
                                    <span className="block text-[10px] text-amber-500 font-bold">Жиры</span>
                                    <span className="text-white font-medium text-sm">{(pendingData.fat || 0).toFixed(1)}</span>
                                </div>
                                <div className="bg-neutral-900 rounded-lg p-2">
                                    <span className="block text-[10px] text-purple-500 font-bold">Угл</span>
                                    <span className="text-white font-medium text-sm">{(pendingData.carbs || 0).toFixed(1)}</span>
                                </div>
                            </div>
                        </div>

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
            </div>
        </div>
    )
}
''')
    print("Fixed.")
