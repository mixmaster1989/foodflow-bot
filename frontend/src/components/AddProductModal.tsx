import { useState, useRef } from 'react'
import { X, Loader2, Sparkles, CheckCircle2, Camera, Mic, Leaf, RefreshCcw } from 'lucide-react'
import { fridgeApi, universalApi } from '../api/client'

interface AddProductModalProps {
    isOpen: boolean
    onClose: () => void
    onSuccess: () => void
}

import { CameraOverlay } from './CameraOverlay'
import { useVoiceRecorder } from '../hooks/useVoiceRecorder'

export function AddProductModal({ isOpen, onClose, onSuccess }: AddProductModalProps) {
    const [step, setStep] = useState<'input' | 'confirm'>('input')
    const [loading, setLoading] = useState(false)
    const [showCamera, setShowCamera] = useState(false)
    const fileInputRef = useRef<HTMLInputElement>(null)
    const { isRecording, startRecording, stopRecording } = useVoiceRecorder()

    // Smart Input State
    const [query, setQuery] = useState('')
    const [isHerbalife, setIsHerbalife] = useState(false)

    // ... (rest of metadata)

    const handleVoiceToggle = async () => {
        if (isRecording) {
            setLoading(true)
            try {
                const audioBlob = await stopRecording()
                if (audioBlob.size < 100) throw new Error('Запись слишком короткая')

                const result = await universalApi.process({ file: audioBlob })
                if (result.success && result.analysis) {
                    setQuery(result.text || '')
                    const analysis = result.analysis
                    if (analysis.type === 'herbalife') {
                        const { product, nutrition } = analysis
                        setFormData({
                            name: product.name,
                            calories: String(Math.round(nutrition.calories)),
                            protein: String(nutrition.protein.toFixed(1)),
                            fat: String(nutrition.fat.toFixed(1)),
                            carbs: String(nutrition.carbs.toFixed(1)),
                            weight_g: String(Math.round(nutrition.weight)),
                            quantity: '1',
                            price: ''
                        })
                        setIsHerbalife(true)
                    } else {
                        const norm = analysis.normalization
                        setFormData({
                            name: norm.name || result.text,
                            calories: String(Math.round(norm.calories || 0)),
                            protein: String((norm.protein || 0).toFixed(1)),
                            fat: String((norm.fat || 0).toFixed(1)),
                            carbs: String((norm.carbs || 0).toFixed(1)),
                            weight_g: String(norm.weight_g || ''),
                            quantity: '1',
                            price: ''
                        })
                        setIsHerbalife(false)
                    }
                    setStep('confirm')
                } else {
                    alert(result.message || 'Не удалось распознать голос')
                }
            } catch (err) {
                alert('Ошибка: ' + (err instanceof Error ? err.message : String(err)))
            } finally {
                setLoading(false)
            }
        } else {
            await startRecording()
        }
    }

    // Analyzed Data State
    const [formData, setFormData] = useState({
        name: '',
        calories: '',
        protein: '',
        fat: '',
        carbs: '',
        weight_g: '',
        quantity: '1',
        price: ''
    })

    if (!isOpen) return null

    const handleAnalyze = async (manualText?: string) => {
        const textToProcess = manualText || query;
        if (!textToProcess.trim()) return
        setLoading(true)
        try {
            const result = await universalApi.process({ text: textToProcess })
            if (result.success && result.analysis) {
                const analysis = result.analysis
                if (analysis.type === 'herbalife') {
                    const { product, nutrition } = analysis
                    setFormData({
                        name: product.name,
                        calories: String(Math.round(nutrition.calories)),
                        protein: String(nutrition.protein.toFixed(1)),
                        fat: String(nutrition.fat.toFixed(1)),
                        carbs: String(nutrition.carbs.toFixed(1)),
                        weight_g: String(Math.round(nutrition.weight)),
                        quantity: '1',
                        price: ''
                    })
                    setIsHerbalife(true)
                } else {
                    const norm = analysis.normalization
                    setFormData({
                        name: norm.name || textToProcess,
                        calories: String(Math.round(norm.calories || 0)),
                        protein: String((norm.protein || 0).toFixed(1)),
                        fat: String((norm.fat || 0).toFixed(1)),
                        carbs: String((norm.carbs || 0).toFixed(1)),
                        weight_g: String(norm.weight_g || ''),
                        quantity: '1',
                        price: ''
                    })
                    setIsHerbalife(false)
                }
                setStep('confirm')
            }
        } catch (err) {
            alert('Не удалось распознать: ' + err)
        } finally {
            setLoading(false)
        }
    }

    const handlePhotoCapture = async (blob: Blob) => {
        setLoading(true)
        setShowCamera(false)
        try {
            const result = await universalApi.process({ file: blob })
            if (result.success && result.analysis) {
                const analysis = result.analysis
                const norm = analysis.normalization
                setFormData({
                    name: norm?.name || result.text || 'Продукт с камеры',
                    calories: String(Math.round(norm?.calories || 0)),
                    protein: String((norm?.protein || 0).toFixed(1)),
                    fat: String((norm?.fat || 0).toFixed(1)),
                    carbs: String((norm?.carbs || 0).toFixed(1)),
                    weight_g: '',
                    quantity: '1',
                    price: ''
                })
                setStep('confirm')
            }
        } catch (err) {
            alert('Ошибка анализа фото')
        } finally {
            setLoading(false)
        }
    }

    const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) return
        setLoading(true)
        try {
            const result = await universalApi.process({ file })
            if (result.success && result.analysis) {
                const analysis = result.analysis
                const norm = analysis.normalization
                setFormData({
                    name: norm?.name || result.text || 'Продукт из памяти',
                    calories: String(Math.round(norm?.calories || 0)),
                    protein: String((norm?.protein || 0).toFixed(1)),
                    fat: String((norm?.fat || 0).toFixed(1)),
                    carbs: String((norm?.carbs || 0).toFixed(1)),
                    weight_g: '',
                    quantity: '1',
                    price: ''
                })
                setStep('confirm')
            }
        } catch (err) {
            alert('Ошибка анализа фото')
        } finally {
            setLoading(false)
        }
    }

    const [consumeImmediately, setConsumeImmediately] = useState(false)

    const handleSave = async () => {
        setLoading(true)
        try {
            // 1. Add Product
            const product = await fridgeApi.addProduct({
                ...formData,
                calories: Number(formData.calories) || 0,
                protein: Number(formData.protein) || 0,
                fat: Number(formData.fat) || 0,
                carbs: Number(formData.carbs) || 0,
                weight_g: Number(formData.weight_g) || 0,
                quantity: Number(formData.quantity) || 1,
                price: Number(formData.price) || 0,
                category: isHerbalife ? 'herbalife' : 'smart_add'
            })

            // 2. Consume Immediately (if checked)
            if (consumeImmediately && product.id) {
                await fridgeApi.consumeProduct(product.id, {
                    amount: 1, // Consume 1 unit (or full weight if tracked by weight? Logic suggests 1 unit for now)
                    unit: 'qty'
                })
            }

            onSuccess()
            handleClose()
        } catch (err) {
            alert('Ошибка добавления: ' + JSON.stringify(err))
        } finally {
            setLoading(false)
        }
    }

    const handleClose = () => {
        setStep('input')
        setQuery('')
        setIsHerbalife(false)
        setFormData({ name: '', calories: '', protein: '', fat: '', carbs: '', weight_g: '', quantity: '1', price: '' })
        onClose()
    }

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target
        setFormData(prev => ({ ...prev, [name]: value }))
    }

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="bg-neutral-900 border border-neutral-800 rounded-3xl w-full max-w-sm p-6 relative overflow-hidden">
                {/* Decoration */}
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-emerald-500 via-blue-500 to-purple-500"></div>

                <button
                    onClick={handleClose}
                    className="absolute top-4 right-4 text-neutral-500 hover:text-white"
                >
                    <X className="w-6 h-6" />
                </button>

                <h2 className="text-xl font-bold mb-4 flex items-center gap-2 text-white">
                    {isHerbalife ? <Leaf className="w-5 h-5 text-emerald-400" /> : <Sparkles className="w-5 h-5 text-emerald-500" />}
                    {step === 'input' ? 'Добавить продукт' : 'Проверьте данные'}
                </h2>

                {step === 'input' ? (
                    <div className="space-y-4">
                        <textarea
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="Что у вас есть? (Текст или фото)"
                            className="w-full bg-neutral-800 border border-neutral-700 rounded-2xl px-5 py-4 text-white focus:outline-none focus:border-emerald-500 min-h-[120px] shadow-inner text-sm leading-relaxed"
                            autoFocus
                        />

                        <div className="flex gap-2">
                            <button
                                onClick={() => setShowCamera(true)}
                                className="flex-1 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 p-3 rounded-xl flex flex-col items-center gap-1 transition-all group"
                            >
                                <Camera className="w-5 h-5 text-neutral-400 group-hover:text-emerald-500" />
                                <span className="text-[10px] text-neutral-500">Live Камера</span>
                            </button>
                            <button
                                onClick={() => fileInputRef.current?.click()}
                                className="flex-1 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 p-3 rounded-xl flex flex-col items-center gap-1 transition-all group"
                            >
                                <RefreshCcw className="w-5 h-5 text-neutral-400 group-hover:text-emerald-500" />
                                <span className="text-[10px] text-neutral-500">Из памяти</span>
                            </button>
                            <button
                                onClick={handleVoiceToggle}
                                className={`flex-1 ${isRecording ? 'bg-red-500/20 border-red-500 animate-pulse' : 'bg-neutral-800 hover:bg-neutral-700 border-neutral-700'} p-3 rounded-xl flex flex-col items-center gap-1 transition-all group`}
                            >
                                <Mic className={`w-5 h-5 ${isRecording ? 'text-red-500' : 'text-neutral-400 group-hover:text-emerald-500'}`} />
                                <span className="text-[10px] text-neutral-500">{isRecording ? 'Стоп' : 'Голос'}</span>
                            </button>
                            <input
                                type="file"
                                ref={fileInputRef}
                                className="hidden"
                                accept="image/*"
                                onChange={handlePhotoUpload}
                            />
                        </div>

                        {showCamera && (
                            <CameraOverlay
                                onCapture={handlePhotoCapture}
                                onClose={() => setShowCamera(false)}
                            />
                        )}

                        <button
                            onClick={() => handleAnalyze()}
                            disabled={loading || !query.trim()}
                            className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-4 rounded-2xl flex items-center justify-center gap-2 transition-all disabled:opacity-50 shadow-lg shadow-emerald-900/20"
                        >
                            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
                            Принять
                        </button>

                        <p className="text-[10px] text-neutral-600 text-center uppercase tracking-widest font-bold">
                            Бесшовная магия AI & Herbalife
                        </p>
                    </div>
                ) : (
                    <div className="space-y-3 animate-in fade-in slide-in-from-bottom-4 duration-300">
                        {isHerbalife && (
                            <div className="bg-emerald-500/10 border border-emerald-500/20 p-3 rounded-xl flex items-start gap-3 mb-2">
                                <Leaf className="w-5 h-5 text-emerald-500 shrink-0" />
                                <div>
                                    <p className="text-[10px] font-bold text-emerald-500 uppercase">HERBALIFE EXPERT</p>
                                    <p className="text-[10px] text-neutral-400 leading-tight">Продукт найден в базе. Данные КБЖУ подставлены автоматически за порцию.</p>
                                </div>
                            </div>
                        )}
                        <div>
                            <label className="block text-xs text-neutral-400 mb-1">Название</label>
                            <input
                                name="name"
                                value={formData.name}
                                onChange={handleChange}
                                className="w-full bg-neutral-800 border border-neutral-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-emerald-500 font-medium"
                            />
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="block text-xs text-neutral-400 mb-1">Вес (г)</label>
                                <input
                                    name="weight_g"
                                    type="number"
                                    value={formData.weight_g}
                                    onChange={handleChange}
                                    placeholder="100"
                                    className="w-full bg-neutral-800 border border-neutral-700 rounded-xl px-4 py-2 text-white"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-neutral-400 mb-1">Цена (₽)</label>
                                <input
                                    name="price"
                                    type="number"
                                    value={formData.price}
                                    onChange={handleChange}
                                    placeholder="0"
                                    className="w-full bg-neutral-800 border border-neutral-700 rounded-xl px-4 py-2 text-white"
                                />
                            </div>
                        </div>

                        <div className="p-3 bg-neutral-800/50 rounded-xl border border-neutral-800">
                            <div className="text-xs text-center text-neutral-500 mb-2 font-medium uppercase tracking-wider">На 100г продукта</div>
                            <div className="grid grid-cols-4 gap-2">
                                {[
                                    { l: 'Ккал', k: 'calories', c: 'text-emerald-400' },
                                    { l: 'Белки', k: 'protein', c: 'text-blue-400' },
                                    { l: 'Жиры', k: 'fat', c: 'text-amber-400' },
                                    { l: 'Угл', k: 'carbs', c: 'text-purple-400' }
                                ].map(f => (
                                    <div key={f.k}>
                                        <label className={`block text-[10px] mb-1 text-center font-bold ${f.c}`}>{f.l}</label>
                                        <input
                                            name={f.k}
                                            type="number"
                                            value={(formData as any)[f.k]}
                                            onChange={handleChange}
                                            className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-1 py-1 text-white text-center text-xs"
                                        />
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Eat Immediately Option */}
                        <div
                            onClick={() => setConsumeImmediately(!consumeImmediately)}
                            className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${consumeImmediately ? 'bg-emerald-500/10 border-emerald-500/50' : 'bg-neutral-800 border-neutral-700 hover:border-neutral-600'}`}
                        >
                            <div className={`w-5 h-5 rounded-md border flex items-center justify-center transition-colors ${consumeImmediately ? 'bg-emerald-500 border-emerald-500' : 'border-neutral-500'}`}>
                                {consumeImmediately && <CheckCircle2 className="w-3.5 h-3.5 text-white" />}
                            </div>
                            <div>
                                <p className={`text-sm font-medium ${consumeImmediately ? 'text-emerald-400' : 'text-neutral-300'}`}>Съесть сразу</p>
                                <p className="text-[10px] text-neutral-500">Добавит в холодильник И сразу запишет в цели</p>
                            </div>
                            <Utensils className={`w-4 h-4 ml-auto ${consumeImmediately ? 'text-emerald-500' : 'text-neutral-600'}`} />
                        </div>

                        <div className="flex gap-2 mt-4 pt-2">
                            <button
                                onClick={() => setStep('input')}
                                className="flex-1 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 font-medium py-3 rounded-xl transition-colors"
                            >
                                Назад
                            </button>
                            <button
                                onClick={handleSave}
                                disabled={loading}
                                className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 transition-colors"
                            >
                                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <CheckCircle2 className="w-5 h-5" />}
                                Готово
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
