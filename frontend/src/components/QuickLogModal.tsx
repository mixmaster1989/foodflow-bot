import { useState, useRef, useEffect } from 'react'
import { X, Mic, Send, Loader2, Scale } from 'lucide-react'
import { universalApi, consumptionApi } from '../api/client'

interface QuickLogModalProps {
    isOpen: boolean
    onClose: () => void
    onSuccess: () => void
}

export function QuickLogModal({ isOpen, onClose, onSuccess }: QuickLogModalProps) {
    const [text, setText] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [stage, setStage] = useState<'input' | 'clarify_weight'>('input')
    const [pendingData, setPendingData] = useState<any>(null)
    const inputRef = useRef<HTMLInputElement>(null)

    useEffect(() => {
        if (isOpen && inputRef.current) {
            setTimeout(() => inputRef.current?.focus(), 100)
        }
        if (!isOpen) {
            // Reset state on close
            setText('')
            setStage('input')
            setPendingData(null)
            setIsLoading(false)
        }
    }, [isOpen])

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!text.trim()) return

        setIsLoading(true)
        try {
            if (stage === 'input') {
                // Step 1: Analyze Text
                const res = await universalApi.process({ text: text })

                if (res.success && res.analysis) {
                    const norm = res.analysis.normalization
                    // intent unused

                    // If it's Herbalife, we might want to just rely on backend parsing (qty_data already there)
                    // But for general food:
                    if (res.analysis.type === 'herbalife') {
                        // TODO: Herbalife usually auto-logs or we need a specific endpoint. 
                        // For now, let's treat it as success if backend returns success.
                        // IMPORTANT: universalApi currently doesn't SAVE.
                        // Correction: We need to manually SAVE.

                        // For Herbalife, the API router usually returns nutrition logic but doesn't save?
                        // Let's assume for MVP we might need to send a "log" request.
                        // But wait, the standard consumption log needs product details.

                        // Shortcut: If we want to move fast, we can call consumptionApi with the parsed data
                        const hProd = res.analysis.product
                        const hNutr = res.analysis.nutrition

                        await consumptionApi.manualLog({
                            product_name: hProd.name,
                            calories: hNutr.calories,
                            protein: hNutr.protein,
                            fat: hNutr.fat,
                            carbs: hNutr.carbs,
                            fiber: hNutr.fiber, // if available
                            weight_g: 0 // Herbalife is Portion based
                        })
                        onSuccess()
                        onClose()
                        return
                    }

                    if (norm) {
                        // Check if weight missing
                        if (norm.weight_missing) {
                            setPendingData(norm)
                            setStage('clarify_weight')
                            setText('') // Clear text for weight input
                            setIsLoading(false)
                            return
                        } else {
                            // Weight present, log it!
                            await consumptionApi.manualLog({
                                product_name: norm.base_name || norm.name,
                                calories: norm.calories,
                                protein: norm.protein,
                                fat: norm.fat,
                                carbs: norm.carbs,
                                fiber: norm.fiber,
                                weight_g: norm.weight_grams
                            })
                            onSuccess()
                            onClose()
                            return
                        }
                    } else {
                        alert(res.message || 'Не удалось распознать еду')
                    }
                } else {
                    alert(res.message || 'Ошибка анализа')
                }
            } else if (stage === 'clarify_weight') {
                // Step 2: Handle Weight Input
                const weight = parseFloat(text.replace(',', '.'))
                if (isNaN(weight) || weight <= 0) {
                    alert('Введите корректный вес')
                    setIsLoading(false)
                    return
                }

                // Calculate final macros
                const factor = weight / 100
                const finalData = {
                    product_name: pendingData.base_name || pendingData.name,
                    calories: (pendingData.calories || 0) * factor,
                    protein: (pendingData.protein || 0) * factor,
                    fat: (pendingData.fat || 0) * factor,
                    carbs: (pendingData.carbs || 0) * factor,
                    fiber: (pendingData.fiber || 0) * factor,
                    weight_g: weight
                }

                await consumptionApi.manualLog(finalData)
                onSuccess()
                onClose()
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
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
                onClick={onClose}
            ></div>

            {/* Modal */}
            <div className="relative w-full max-w-md bg-neutral-900 border border-neutral-800 rounded-3xl p-6 shadow-2xl transform transition-all animate-in fade-in slide-in-from-bottom-4">
                <button
                    onClick={onClose}
                    className="absolute right-4 top-4 text-neutral-500 hover:text-white transition-colors"
                >
                    <X className="w-6 h-6" />
                </button>

                <div className="mb-6">
                    <h2 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-indigo-500 bg-clip-text text-transparent flex items-center gap-2">
                        {stage === 'input' ? '⚡ Быстрая запись' : '⚖️ Уточните вес'}
                    </h2>
                    <p className="text-neutral-400 text-sm mt-1">
                        {stage === 'input'
                            ? 'Например: "Яблоко 150г" или просто "Яблоко"'
                            : `Я понял, это ${pendingData?.base_name || pendingData?.name}. Сколько грамм?`
                        }
                    </p>
                </div>

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
                            className={`w-full bg-neutral-800/50 border border-neutral-700 rounded-2xl pl-4 pr-12 py-4 text-lg focus:outline-none focus:border-blue-500 transition-all text-white placeholder:text-neutral-600 ${stage === 'clarify_weight' ? 'pl-11' : ''}`}
                            disabled={isLoading}
                            autoComplete="off"
                            type={stage === 'clarify_weight' ? 'number' : 'text'}
                        />

                        {stage === 'input' && !text && (
                            <button type="button" className="absolute right-3 top-1/2 -translate-y-1/2 p-2 text-neutral-500 hover:text-white transition-colors">
                                <Mic className="w-5 h-5" />
                            </button>
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
            </div>
        </div>
    )
}
