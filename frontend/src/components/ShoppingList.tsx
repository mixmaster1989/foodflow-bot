import { useState, useEffect } from 'react'
import { ShoppingBasket, CheckCircle2, Circle, Trash2, Plus, Loader2 } from 'lucide-react'
import { shoppingApi } from '../api/client'

interface ShoppingListProps {
    onBought: () => void // Signal to refresh fridge if item bought
}

export function ShoppingList({ onBought }: ShoppingListProps) {
    const [items, setItems] = useState<any[]>([])
    const [loading, setLoading] = useState(false)
    const [newItemName, setNewItemName] = useState('')

    const fetchList = async () => {
        setLoading(true)
        try {
            const data = await shoppingApi.getList()
            setItems(data.items || [])
        } catch (err) {
            console.error('Fetch shopping list error:', err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchList()
    }, [])

    const handleAddField = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!newItemName.trim()) return
        try {
            await shoppingApi.addItem(newItemName)
            setNewItemName('')
            fetchList()
        } catch (err) {
            alert('Ошибка добавления')
        }
    }

    const handleToggle = async (id: number) => {
        try {
            await shoppingApi.toggleBought(id)
            fetchList()
            onBought() // Refresh fridge
        } catch (err) {
            alert('Ошибка обновления')
        }
    }

    const handleDelete = async (id: number) => {
        try {
            await shoppingApi.deleteItem(id)
            fetchList()
        } catch (err) {
            alert('Ошибка удаления')
        }
    }

    return (
        <div className="animate-in fade-in slide-in-from-right-4 duration-300">
            <h2 className="font-semibold text-lg flex items-center gap-2 mb-4">
                <ShoppingBasket className="w-5 h-5 text-blue-500" /> Список покупок
            </h2>

            {/* Quick Add */}
            <form onSubmit={handleAddField} className="flex gap-2 mb-6">
                <input
                    value={newItemName}
                    onChange={(e) => setNewItemName(e.target.value)}
                    placeholder="Что купить? (например: Молоко)"
                    className="flex-1 bg-neutral-900 border border-neutral-800 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                />
                <button
                    type="submit"
                    className="bg-blue-600 p-2 rounded-xl text-white hover:bg-blue-500 transition-colors"
                >
                    <Plus className="w-5 h-5" />
                </button>
            </form>

            {loading && items.length === 0 ? (
                <div className="flex justify-center p-8">
                    <Loader2 className="w-6 h-6 animate-spin text-neutral-600" />
                </div>
            ) : items.length > 0 ? (
                <div className="space-y-2">
                    {items.map((item) => (
                        <div
                            key={item.id}
                            className={`flex items-center justify-between p-4 rounded-2xl border transition-all ${item.is_bought
                                    ? 'bg-neutral-900/10 border-neutral-900 opacity-50'
                                    : 'bg-neutral-900/50 border-neutral-800'
                                }`}
                        >
                            <div className="flex items-center gap-3">
                                <button onClick={() => handleToggle(item.id)} className="text-neutral-500">
                                    {item.is_bought ? (
                                        <CheckCircle2 className="w-5 h-5 text-blue-500" />
                                    ) : (
                                        <Circle className="w-5 h-5" />
                                    )}
                                </button>
                                <span className={`text-sm ${item.is_bought ? 'line-through text-neutral-600' : 'text-neutral-200'}`}>
                                    {item.product_name}
                                </span>
                            </div>
                            <button
                                onClick={() => handleDelete(item.id)}
                                className="p-1 text-neutral-600 hover:text-red-500 transition-colors"
                            >
                                <Trash2 className="w-4 h-4" />
                            </button>
                        </div>
                    ))}
                </div>
            ) : (
                <div className="p-8 text-center bg-neutral-900/30 border border-dashed border-neutral-800 rounded-3xl">
                    <p className="text-neutral-500 text-sm">Список пуст</p>
                </div>
            )}
        </div>
    )
}
