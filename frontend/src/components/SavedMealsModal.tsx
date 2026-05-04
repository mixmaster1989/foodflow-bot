import { useState, useEffect } from 'react';
import { useToast } from '../components/Toast'
import { X, Loader2, Star, Trash2 } from 'lucide-react';
import { savedDishesApi, consumptionApi } from '../api/client';

interface SavedMealsModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSuccess: () => void;
    onSelectMeal?: (meal: any) => void;
}

export function SavedMealsModal({ isOpen, onClose, onSuccess }: SavedMealsModalProps) {
    const toast = useToast()
    const [meals, setMeals] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isLogging, setIsLogging] = useState<number | null>(null);

    const fetchMeals = async () => {
        setIsLoading(true);
        try {
            const data = await savedDishesApi.getList();
            setMeals(data);
        } catch (err) {
            console.error(err);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        if (isOpen) {
            fetchMeals();
        }
    }, [isOpen]);

    const handleDelete = async (id: number) => {
        if (!confirm('Удалить это блюдо?')) return;
        try {
            await savedDishesApi.delete(id);
            fetchMeals();
        } catch (err) {
            toast.error('Ошибка при удалении');
        }
    };

    const handleLog = async (id: number) => {
        const meal = meals.find(m => m.id === id);
        if (!meal) return;

        setIsLogging(id);
        try {
            await consumptionApi.manualLog({
                product_name: meal.name,
                calories: meal.total_calories,
                protein: meal.total_protein,
                fat: meal.total_fat,
                carbs: meal.total_carbs,
                fiber: meal.total_fiber || 0,
                date: new Date().toISOString()
            });
            onSuccess();
            onClose();
        } catch (err) {
            toast.error('Ошибка сохранения блюда');
        } finally {
            setIsLogging(null);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center p-4 sm:p-0">
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity" onClick={onClose}></div>
            <div className="relative w-full max-w-md bg-neutral-900 border border-neutral-800 rounded-3xl p-6 shadow-2xl flex flex-col max-h-[90vh] animate-in fade-in slide-in-from-bottom-4">
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-xl font-bold bg-gradient-to-r from-amber-400 to-orange-500 bg-clip-text text-transparent flex items-center gap-2">
                        <Star className="w-5 h-5 text-amber-500 fill-amber-500" /> Мои блюда
                    </h2>
                    <button onClick={onClose} className="text-neutral-500 hover:text-white transition-colors">
                        <X className="w-6 h-6" />
                    </button>
                </div>

                <div className="overflow-y-auto flex-1 no-scrollbar space-y-3 pb-2">
                    {isLoading ? (
                        <div className="flex justify-center p-8">
                            <Loader2 className="w-6 h-6 text-emerald-500 animate-spin" />
                        </div>
                    ) : meals.length === 0 ? (
                        <div className="text-center p-8 bg-neutral-800/50 rounded-2xl border border-dashed border-neutral-700">
                            <Star className="w-8 h-8 text-neutral-600 mx-auto mb-2" />
                            <p className="text-neutral-400 font-medium">У вас пока нет сохранённых блюд.</p>
                            <p className="text-neutral-500 text-xs mt-1">Здесь будут отображаться ваши сохранённые блюда.</p>
                        </div>
                    ) : (
                        meals.map(meal => (
                            <div key={meal.id} className="bg-neutral-800/50 border border-neutral-700 p-4 rounded-xl flex flex-col">
                                <div className="flex justify-between items-start mb-2">
                                    <h3 className="text-white font-semibold text-lg">{meal.name}</h3>
                                    <button onClick={() => handleDelete(meal.id)} className="text-neutral-500 hover:text-red-500 p-1">
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                                <div className="text-xs text-neutral-400 mb-3 line-clamp-2">
                                    {meal.components.map((c: any) => `${c.name} (${c.weight_g || 1}г)`).join(', ')}
                                </div>
                                <div className="flex justify-between items-center mt-auto">
                                    <div className="flex gap-3 text-sm">
                                        <span className="text-emerald-400 font-bold">{Math.round(meal.total_calories)} Ккал</span>
                                        <span className="text-blue-400">Б: {Math.round(meal.total_protein)}</span>
                                        <span className="text-amber-400">Ж: {Math.round(meal.total_fat)}</span>
                                        <span className="text-purple-400">У: {Math.round(meal.total_carbs)}</span>
                                    </div>
                                    <button
                                        onClick={() => handleLog(meal.id)}
                                        disabled={isLogging === meal.id}
                                        className="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-xl text-xs font-bold transition-all disabled:opacity-50"
                                    >
                                        {isLogging === meal.id ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : 'Записать'}
                                    </button>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}
