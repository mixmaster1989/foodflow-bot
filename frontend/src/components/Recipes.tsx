import React, { useState, useEffect } from 'react';
import { Home, Lock, ChefHat, RefreshCw, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { recipesApi } from '../api/client';

interface RecipesProps {
    onNavigate: (tab: any) => void;
}

import { useAuth } from '../hooks/useAuth';
import { useToast } from '../components/Toast';

export const Recipes: React.FC<RecipesProps> = ({ onNavigate }) => {
    const { isFree, isPro } = useAuth();
    const toast = useToast();

    const [categories, setCategories] = useState<string[]>([]);
    const [activeCategory, setActiveCategory] = useState<string>('');
    const [recipes, setRecipes] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [expandedRecipe, setExpandedRecipe] = useState<number | null>(null);

    useEffect(() => {
        if (!isFree) {
            recipesApi.getCategories().then(res => {
                if (res.categories && res.categories.length > 0) {
                    setCategories(res.categories);
                    setActiveCategory(res.categories[0]);
                }
            }).catch(console.error);
        }
    }, [isFree]);

    useEffect(() => {
        if (activeCategory && !isFree) {
            handleGenerate(activeCategory, false);
        }
    }, [activeCategory, isFree]);

    const handleGenerate = async (category: string, refresh: boolean) => {
        if (refresh && !isPro) {
            toast.info('Обновление рецептов через AI доступно только в тарифе PRO');
            return;
        }
        setIsLoading(true);
        try {
            const data = await recipesApi.generateRecipes(category, refresh);
            setRecipes(data);
            setExpandedRecipe(null);
        } catch (e) {
            console.error(e);
            toast.error('Ошибка загрузки рецептов');
        } finally {
            setIsLoading(false);
        }
    };

    const toggleRecipe = (idx: number) => {
        setExpandedRecipe(prev => (prev === idx ? null : idx));
    };

    return (
        <div className="pb-24 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center gap-2 mb-6 cursor-pointer" onClick={() => onNavigate('dashboard')}>
                <Home className="w-5 h-5 text-emerald-500" />
                <span className="text-emerald-500 font-medium text-sm">На главную</span>
            </div>

            <div className="flex justify-between items-center mb-6">
                <h2 className="font-semibold text-xl flex items-center gap-2 text-white">
                    <ChefHat className="w-6 h-6 text-amber-500" /> Рецепты
                </h2>
            </div>

            {isFree ? (
                <div className="flex flex-col items-center justify-center p-8 bg-neutral-900/50 backdrop-blur-md border border-amber-500/20 rounded-3xl text-center shadow-lg relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-amber-500/10 blur-[60px] rounded-full pointer-events-none"></div>
                    <div className="w-20 h-20 bg-neutral-950 rounded-full flex items-center justify-center mb-4 border border-white/5 relative z-10">
                        <Lock className="w-10 h-10 text-neutral-500" />
                    </div>
                    <h3 className="text-xl font-bold text-white mb-2 relative z-10">Доступ закрыт</h3>
                    <p className="text-neutral-400 text-sm mb-6 relative z-10">
                        Умный генератор рецептов из ваших продуктов доступен только по подписке.
                    </p>
                    <button
                        onClick={() => onNavigate('subscriptions')}
                        className="w-full max-w-[200px] bg-gradient-to-r from-amber-500 to-orange-400 text-white font-bold py-3 px-6 rounded-2xl shadow-lg relative z-10 active:scale-95 transition-transform"
                    >
                        💎 Оформить подписку
                    </button>
                </div>
            ) : (
                <>
                    {/* Categories Router */}
                    <div className="flex gap-2 mb-6 overflow-x-auto pb-2 no-scrollbar">
                        {categories.map((cat, idx) => (
                            <button
                                key={idx}
                                onClick={() => setActiveCategory(cat)}
                                className={`flex-shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-all ${activeCategory === cat
                                    ? 'bg-amber-500 text-neutral-950 shadow-[0_0_15px_rgba(245,158,11,0.4)]'
                                    : 'bg-neutral-900 border border-neutral-800 text-neutral-400 hover:text-white hover:border-amber-500/50'
                                    }`}
                            >
                                {cat}
                            </button>
                        ))}
                    </div>

                    <div className="flex justify-between items-center mb-4">
                        <span className="text-xs font-bold text-neutral-500 uppercase tracking-widest">Из вашего холодильника</span>
                        <button
                            onClick={() => handleGenerate(activeCategory, true)}
                            disabled={isLoading}
                            className={`flex items-center gap-1.5 text-xs text-amber-500 hover:text-amber-400 transition-colors bg-amber-500/10 px-3 py-1.5 rounded-full disabled:opacity-50 ${!isPro ? 'grayscale opacity-70' : ''}`}
                        >
                            {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : isPro ? <RefreshCw className="w-3.5 h-3.5" /> : <Lock className="w-3 h-3" />}
                            {isPro ? 'Обновить' : 'AI Обновление (PRO)'}
                        </button>
                    </div>

                    {/* Recipes List */}
                    {isLoading && !recipes.length ? (
                        <div className="space-y-4">
                            {[1, 2].map(i => (
                                <div key={i} className="h-40 bg-neutral-900/50 border border-neutral-800 rounded-3xl animate-pulse"></div>
                            ))}
                        </div>
                    ) : recipes.length > 0 ? (
                        <div className="space-y-4">
                            {recipes.map((recipe, idx) => {
                                const isExpanded = expandedRecipe === idx;
                                return (
                                    <div key={idx} className="bg-neutral-900/50 border border-neutral-800/50 rounded-3xl overflow-hidden transition-all hover:border-amber-500/30">
                                        <div
                                            className="p-5 cursor-pointer flex justify-between items-start"
                                            onClick={() => toggleRecipe(idx)}
                                        >
                                            <div className="pr-4">
                                                <h3 className="font-bold text-lg text-white mb-1 leading-tight">{recipe.title}</h3>
                                                <p className="text-amber-400 text-xs font-bold uppercase tracking-widest">{recipe.calories} ккал</p>
                                            </div>
                                            <div className="w-8 h-8 rounded-full bg-neutral-800 flex items-center justify-center flex-shrink-0 text-neutral-400">
                                                {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
                                            </div>
                                        </div>

                                        {isExpanded && (
                                            <div className="px-5 pb-5 pt-2 border-t border-neutral-800/50 animate-in slide-in-from-top-2 duration-200">
                                                {recipe.description && (
                                                    <p className="text-neutral-400 text-sm italic mb-4">"{recipe.description}"</p>
                                                )}
                                                <div className="mb-4">
                                                    <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-widest mb-2">Ингредиенты</h4>
                                                    <ul className="text-sm text-neutral-300 space-y-1">
                                                        {recipe.ingredients?.map((ing: any, i: number) => (
                                                            <li key={i} className="flex items-start gap-2">
                                                                <span className="text-amber-500 mt-0.5">•</span>
                                                                <span><b>{ing.name}</b> {ing.amount}</span>
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                                <div>
                                                    <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-widest mb-2">Шаги</h4>
                                                    <ol className="text-sm text-neutral-300 space-y-2 list-decimal list-inside">
                                                        {recipe.steps?.map((step: string, i: number) => (
                                                            <li key={i} className="pl-1"><span className="pl-1">{step}</span></li>
                                                        ))}
                                                    </ol>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    ) : (
                        !isLoading && (
                            <div className="text-center p-8 text-neutral-500">
                                Не удалось сгенерировать рецепты. Попробуйте обновить.
                            </div>
                        )
                    )}
                </>
            )}
        </div>
    );
};
