import { useState, useEffect } from 'react'
import { useToast } from '../components/Toast'
import { History, X, Loader2, Edit2, Trash2, Check } from 'lucide-react'
import { consumptionApi } from '../api/client'

interface ConsumptionHistoryProps {
    isOpen: boolean
    onClose: () => void
    targetDate?: Date
}

export function ConsumptionHistory({ isOpen, onClose, targetDate }: ConsumptionHistoryProps) {
    const toast = useToast()
    const [logs, setLogs] = useState<any[]>([])
    const [loading, setLoading] = useState(false)
    const [editingId, setEditingId] = useState<number | null>(null)
    const [editValues, setEditValues] = useState<any>(null)
    const [isSaving, setIsSaving] = useState(false)

    const fetchLogs = async () => {
        setLoading(true)
        try {
            const params = targetDate
                ? { date: targetDate.toLocaleDateString('en-CA') }
                : { days: 3 };
            const data = await consumptionApi.getLogs(params);
            setLogs(data || [])
        } catch (err) {
            console.error('Fetch consumption logs error:', err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        if (isOpen) fetchLogs()
    }, [isOpen, targetDate])

    const handleEditStart = (log: any) => {
        setEditingId(log.id)
        setEditValues({
            product_name: log.product_name,
            calories: log.calories,
            protein: log.protein,
            fat: log.fat,
            carbs: log.carbs,
            fiber: log.fiber || 0,
            time: new Date(log.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
        })
    }

    const handleSave = async (id: number) => {
        setIsSaving(true)
        try {
            // Prepare data for API
            const updateData: any = { ...editValues }

            // Handle time update
            if (editValues.time) {
                const log = logs.find(l => l.id === id)
                if (log) {
                    const [hours, minutes] = editValues.time.split(':')
                    const newDate = new Date(log.date)
                    newDate.setHours(parseInt(hours), parseInt(minutes))
                    updateData.date = newDate.toISOString()
                }
            }
            delete updateData.time

            await consumptionApi.updateLog(id, updateData)
            setEditingId(null)
            fetchLogs()
        } catch (err) {
            console.error('Update log error:', err)
            toast.error('Ошибка при сохранении')
        } finally {
            setIsSaving(false)
        }
    }

    const handleDelete = async (id: number) => {
        if (!window.confirm('Удалить эту запись?')) return
        try {
            await consumptionApi.deleteLog(id)
            fetchLogs()
        } catch (err) {
            console.error('Delete log error:', err)
        }
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/80 backdrop-blur-sm p-4">
            <div className="bg-neutral-950 border border-neutral-800 rounded-t-[2.5rem] w-full max-w-sm h-[80vh] flex flex-col animate-in slide-in-from-bottom-full duration-500">
                <div className="p-6 flex items-center justify-between border-b border-neutral-900">
                    <h2 className="text-xl font-bold flex items-center gap-2 text-white">
                        <History className="w-6 h-6 text-emerald-500" /> История
                    </h2>
                    <button onClick={onClose} className="p-2 text-neutral-500 hover:text-white">
                        <X className="w-6 h-6" />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                    {loading ? (
                        <div className="flex justify-center p-12">
                            <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
                        </div>
                    ) : logs.length > 0 ? (
                        logs.map((log) => (
                            <div key={log.id} className="p-4 bg-neutral-900 rounded-2xl border border-neutral-800 relative group">
                                {editingId === log.id ? (
                                    <div className="space-y-3">
                                        <input
                                            type="text"
                                            value={editValues.product_name}
                                            onChange={(e) => setEditValues({ ...editValues, product_name: e.target.value })}
                                            className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-2 py-1 text-sm text-white focus:outline-none focus:border-emerald-500"
                                        />
                                        <div className="flex gap-2">
                                            <input
                                                type="time"
                                                value={editValues.time}
                                                onChange={(e) => setEditValues({ ...editValues, time: e.target.value })}
                                                className="bg-neutral-800 border border-neutral-700 rounded-lg px-2 py-1 text-xs text-white"
                                            />
                                            <input
                                                type="number"
                                                value={editValues.calories}
                                                onChange={(e) => setEditValues({ ...editValues, calories: parseFloat(e.target.value) })}
                                                placeholder="ккал"
                                                className="w-20 bg-neutral-800 border border-neutral-700 rounded-lg px-2 py-1 text-xs text-white"
                                            />
                                        </div>
                                        <div className="grid grid-cols-4 gap-2">
                                            {['protein', 'fat', 'carbs', 'fiber'].map(field => (
                                                <div key={field} className="flex flex-col">
                                                    <span className="text-[8px] text-neutral-500 uppercase">{field === 'protein' ? 'Б' : field === 'fat' ? 'Ж' : field === 'carbs' ? 'У' : 'К'}</span>
                                                    <input
                                                        type="number"
                                                        value={editValues[field]}
                                                        onChange={(e) => setEditValues({ ...editValues, [field]: parseFloat(e.target.value) })}
                                                        className="bg-neutral-800 border border-neutral-700 rounded-lg px-2 py-1 text-xs text-white"
                                                    />
                                                </div>
                                            ))}
                                        </div>
                                        <div className="flex justify-end gap-2 mt-2">
                                            <button
                                                onClick={() => setEditingId(null)}
                                                className="px-3 py-1 text-xs text-neutral-400 hover:text-white"
                                            >
                                                Отмена
                                            </button>
                                            <button
                                                onClick={() => handleSave(log.id)}
                                                disabled={isSaving}
                                                className="bg-emerald-600 text-white px-3 py-1 rounded-lg text-xs font-bold flex items-center gap-1"
                                            >
                                                {isSaving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
                                                Сохранить
                                            </button>
                                        </div>
                                    </div>
                                ) : (
                                    <>
                                        <div className="flex justify-between items-start mb-2 pr-2">
                                            <span className="font-bold text-sm text-white leading-tight">{log.product_name}</span>
                                            <span className="text-[10px] text-neutral-500 bg-neutral-800 px-2 py-0.5 rounded-full flex-shrink-0">{new Date(log.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                        </div>
                                        <div className="grid grid-cols-5 gap-1 text-[9px]">
                                            <div className="text-emerald-500 font-bold">{Math.round(log.calories)} ккал</div>
                                            <div className="text-blue-400">Б: {log.protein}</div>
                                            <div className="text-amber-400">Ж: {log.fat}</div>
                                            <div className="text-purple-400">У: {log.carbs}</div>
                                            <div className="text-emerald-600">Кл: {log.fiber || 0}</div>
                                        </div>

                                        {/* Actions */}
                                        <div className="flex gap-2 pt-2 border-t border-neutral-800/50 mt-4">
                                            <button
                                                onClick={() => handleEditStart(log)}
                                                className="flex-1 flex items-center justify-center gap-2 py-2 px-3 bg-neutral-800 hover:bg-neutral-700 text-neutral-200 rounded-xl text-[11px] font-bold transition-all active:scale-95"
                                            >
                                                <Edit2 className="w-3.5 h-3.5 text-blue-400" />
                                                ИЗМЕНИТЬ
                                            </button>
                                            <button
                                                onClick={() => handleDelete(log.id)}
                                                className="flex items-center justify-center gap-2 py-2 px-3 bg-neutral-800 hover:bg-red-500/10 text-neutral-500 hover:text-red-400 rounded-xl text-xs font-semibold transition-all active:scale-95"
                                            >
                                                <Trash2 className="w-3.5 h-3.5" />
                                                УДАЛИТЬ
                                            </button>
                                        </div>
                                    </>
                                )}
                            </div>
                        ))
                    ) : (
                        <div className="p-12 text-center text-neutral-600">
                            Вы еще ничего не ели за последние дни
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
