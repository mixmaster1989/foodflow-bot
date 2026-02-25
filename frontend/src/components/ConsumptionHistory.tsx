import { useState, useEffect } from 'react'
import { History, X, Loader2 } from 'lucide-react'
import { consumptionApi } from '../api/client'

interface ConsumptionHistoryProps {
    isOpen: boolean
    onClose: () => void
}

export function ConsumptionHistory({ isOpen, onClose }: ConsumptionHistoryProps) {
    const [logs, setLogs] = useState<any[]>([])
    const [loading, setLoading] = useState(false)

    const fetchLogs = async () => {
        setLoading(true)
        try {
            const data = await consumptionApi.getLogs(3) // Fetch last 3 days
            setLogs(data || [])
        } catch (err) {
            console.error('Fetch consumption logs error:', err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        if (isOpen) fetchLogs()
    }, [isOpen])

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
                        logs.map((log, idx) => (
                            <div key={log.id || idx} className="p-4 bg-neutral-900 rounded-2xl border border-neutral-800">
                                <div className="flex justify-between items-start mb-2">
                                    <span className="font-medium text-sm text-neutral-200">{log.product_name}</span>
                                    <span className="text-[10px] text-neutral-500">{new Date(log.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                </div>
                                <div className="grid grid-cols-4 gap-2 text-[10px]">
                                    <div className="text-emerald-500 font-bold">{Math.round(log.calories)} ккал</div>
                                    <div className="text-blue-400">Б: {log.protein}</div>
                                    <div className="text-amber-400">Ж: {log.fat}</div>
                                    <div className="text-purple-400">У: {log.carbs}</div>
                                </div>
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
