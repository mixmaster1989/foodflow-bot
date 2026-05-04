import React, { useState } from 'react';
import { useToast } from '../components/Toast'
import { X, Check, Trash2, Package, Flame, LogOut } from 'lucide-react';
import { receiptsApi } from '../api/client';

interface ReceiptItem {
    name: string;
    price: number;
    quantity: number;
    category?: string;
    calories: number;
    protein: number;
    fat: number;
    carbs: number;
    fiber: number;
}

interface ReceiptReviewModalProps {
    receiptId: number;
    items: ReceiptItem[];
    total: number;
    onClose: () => void;
    onFinished: () => void;
}

const ReceiptReviewModal: React.FC<ReceiptReviewModalProps> = ({
    receiptId,
    items: initialItems,
    total,
    onClose,
    onFinished
}) => {
    const toast = useToast()
    const [items, setItems] = useState<ReceiptItem[]>(initialItems);
    const [addedIndices, setAddedIndices] = useState<Set<number>>(new Set());
    const [loadingIndex, setLoadingIndex] = useState<number | null>(null);

    const handleAdd = async (item: ReceiptItem, index: number) => {
        setLoadingIndex(index);
        try {
            await receiptsApi.addItem(receiptId, item);
            setAddedIndices(prev => new Set(prev).add(index));
        } catch (error) {
            console.error('Failed to add item:', error);
            toast.error('Ошибка при добавлении товара');
        } finally {
            setLoadingIndex(null);
        }
    };

    const handleRemove = (index: number) => {
        setItems(prev => prev.filter((_, i) => i !== index));
        // Also adjust addedIndices if necessary, but since we re-calculate indices on filter,
        // it's safer to just remove it from items.
        // If it was already added, it's already in the DB.
    };

    return (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="w-full max-w-2xl max-h-[90vh] glass-effect rounded-3xl overflow-hidden flex flex-col shadow-2xl border border-white/20">
                {/* Header */}
                <div className="p-6 border-b border-white/10 flex items-center justify-between bg-white/5">
                    <div>
                        <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                            <Package className="w-6 h-6 text-blue-400" />
                            Проверка чека #{receiptId}
                        </h2>
                        <p className="text-white/60 text-sm mt-1">
                            Найдено {items.length} позиций на сумму {total}₽
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-white/10 rounded-full transition-colors text-white/70 hover:text-white"
                    >
                        <X className="w-6 h-6" />
                    </button>
                </div>

                {/* Scrollable Content */}
                <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
                    {items.map((item, index) => {
                        const isAdded = addedIndices.has(index);

                        return (
                            <div
                                key={`${item.name}-${index}`}
                                className={`p-4 rounded-2xl border transition-all duration-300 ${isAdded
                                        ? 'bg-green-500/10 border-green-500/30 opacity-70'
                                        : 'bg-white/5 border-white/10 hover:bg-white/10'
                                    }`}
                            >
                                <div className="flex items-start justify-between gap-4">
                                    <div className="flex-1">
                                        <h3 className="font-semibold text-white text-lg leading-tight">
                                            {item.name}
                                        </h3>
                                        <div className="flex flex-wrap gap-3 mt-2">
                                            <span className="text-white/40 text-sm flex items-center gap-1">
                                                💰 {item.price}₽
                                            </span>
                                            <span className="text-white/40 text-sm flex items-center gap-1">
                                                ⚖️ {item.quantity} шт
                                            </span>
                                            <span className="text-blue-400/80 text-sm font-medium flex items-center gap-1">
                                                <Flame className="w-3 h-3" />
                                                {item.calories} ккал
                                            </span>
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-2">
                                        {!isAdded ? (
                                            <>
                                                <button
                                                    onClick={() => handleRemove(index)}
                                                    className="p-2.5 bg-red-500/20 text-red-400 hover:bg-red-500/30 rounded-xl transition-all border border-red-500/20"
                                                    title="Удалить из списка"
                                                >
                                                    <Trash2 className="w-5 h-5" />
                                                </button>
                                                <button
                                                    onClick={() => handleAdd(item, index)}
                                                    disabled={loadingIndex === index}
                                                    className="px-4 py-2.5 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white rounded-xl font-medium transition-all shadow-lg shadow-blue-500/20 flex items-center gap-2"
                                                >
                                                    {loadingIndex === index ? (
                                                        <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                                    ) : (
                                                        <Check className="w-5 h-5" />
                                                    )}
                                                    Добавить
                                                </button>
                                            </>
                                        ) : (
                                            <div className="flex items-center gap-2 px-3 py-1.5 bg-green-500/20 text-green-400 rounded-xl border border-green-500/20 animate-in zoom-in duration-300">
                                                <Check className="w-4 h-4" />
                                                <span className="text-sm font-medium">В холодильнике</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        );
                    })}

                    {items.length === 0 && (
                        <div className="py-12 text-center">
                            <Package className="w-16 h-16 text-white/10 mx-auto mb-4" />
                            <p className="text-white/40 text-lg">Список пуст</p>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-6 border-t border-white/10 bg-white/5 flex items-center justify-between">
                    <p className="text-white/40 text-sm italic">
                        Нажимайте «Добавить» для каждого товара
                    </p>
                    <button
                        onClick={onFinished}
                        className="px-8 py-3 bg-white text-slate-900 rounded-2xl font-bold hover:bg-white/90 transition-all shadow-xl shadow-white/10 flex items-center gap-2"
                    >
                        Готово
                        <LogOut className="w-5 h-5" />
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ReceiptReviewModal;
