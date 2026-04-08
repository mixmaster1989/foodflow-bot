import React, { useState, useEffect } from 'react'
import { Search, Loader2, Leaf, Info, Activity, AlertTriangle, ChevronRight } from 'lucide-react'
import { herbalifeApi } from '../api/client'

interface HerbalifeCatalogProps { }

export const HerbalifeCatalog: React.FC<HerbalifeCatalogProps> = () => {
    const [products, setProducts] = useState<any[]>([])
    const [search, setSearch] = useState('')
    const [isLoading, setIsLoading] = useState(true)
    const [selectedCategory, setSelectedCategory] = useState<string | null>(null)

    useEffect(() => {
        const fetchProducts = async () => {
            try {
                const res = await herbalifeApi.getProducts()
                setProducts(res.products || [])
            } catch (err) {
                console.error('Failed to fetch HL products:', err)
            } finally {
                setIsLoading(false)
            }
        }
        fetchProducts()
    }, [])

    const categories = Array.from(new Set(products.map(p => p.category))).filter(Boolean)

    const filteredProducts = products.filter(p => {
        const matchesSearch = p.name.toLowerCase().includes(search.toLowerCase()) ||
            p.aliases?.some((a: string) => a.toLowerCase().includes(search.toLowerCase()))
        const matchesCategory = !selectedCategory || p.category === selectedCategory
        return matchesSearch && matchesCategory
    })

    if (isLoading) {
        return (
            <div className="flex flex-col items-center justify-center py-20 text-emerald-500">
                <Loader2 className="w-10 h-10 animate-spin mb-4" />
                <p className="text-neutral-500 animate-pulse font-medium">Загрузка базы эксперта...</p>
            </div>
        )
    }

    return (
        <div className="space-y-6 animate-in fade-in duration-500 pb-24">
            <header className="flex flex-col gap-4">
                <div className="flex items-center gap-2">
                    <div className="w-10 h-10 bg-emerald-500/10 rounded-xl flex items-center justify-center border border-emerald-500/20">
                        <Leaf className="w-6 h-6 text-emerald-500" />
                    </div>
                    <div>
                        <h2 className="text-xl font-bold text-white">Каталог Herbalife</h2>
                        <p className="text-neutral-500 text-xs">Официальная база продукции и дозировок</p>
                    </div>
                </div>

                <div className="relative">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-neutral-500" />
                    <input
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Поиск продукта или вкуса..."
                        className="w-full bg-neutral-900 border border-neutral-800 rounded-2xl pl-12 pr-4 py-4 text-white focus:outline-none focus:border-emerald-500 transition-all shadow-xl"
                    />
                </div>

                <div className="flex gap-2 overflow-x-auto no-scrollbar py-1">
                    <button
                        onClick={() => setSelectedCategory(null)}
                        className={`flex-shrink-0 px-4 py-2 rounded-xl text-xs font-bold transition-all border ${!selectedCategory ? 'bg-emerald-600 border-emerald-500 text-white shadow-lg' : 'bg-neutral-900 border-neutral-800 text-neutral-400 hover:text-white'}`}
                    >
                        Все
                    </button>
                    {categories.map(cat => (
                        <button
                            key={cat}
                            onClick={() => setSelectedCategory(cat)}
                            className={`flex-shrink-0 px-4 py-2 rounded-xl text-xs font-bold transition-all border ${selectedCategory === cat ? 'bg-emerald-600 border-emerald-500 text-white shadow-lg' : 'bg-neutral-900 border-neutral-800 text-neutral-400 hover:text-white'}`}
                        >
                            {cat}
                        </button>
                    ))}
                </div>
            </header>

            <div className="grid grid-cols-1 gap-4">
                {filteredProducts.map(product => (
                    <div
                        key={product.id}
                        className="glass-panel group rounded-3xl p-5 border border-white/5 hover:border-emerald-500/30 transition-all relative overflow-hidden active:scale-[0.98]"
                    >
                        <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 blur-[50px] rounded-full group-hover:bg-emerald-500/10 transition-colors"></div>

                        <div className="flex justify-between items-start mb-3 relative">
                            <div className="flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="text-[10px] font-black text-emerald-500 uppercase tracking-widest bg-emerald-500/10 px-2 py-0.5 rounded-md">
                                        {product.subcategory || product.category}
                                    </span>
                                    {product.sku !== "0000" && (
                                        <span className="text-[9px] text-neutral-600 font-mono">SKU: {product.sku}</span>
                                    )}
                                </div>
                                <h3 className="font-bold text-white text-lg group-hover:text-emerald-400 transition-colors">{product.name}</h3>
                            </div>
                        </div>

                        <p className="text-neutral-400 text-xs mb-4 line-clamp-2 leading-relaxed italic">
                            {product.description}
                        </p>

                        <div className="grid grid-cols-2 gap-4 mb-4">
                            <div className="bg-white/5 rounded-2xl p-3 border border-white/5">
                                <div className="flex items-center gap-2 text-[10px] text-neutral-500 uppercase font-bold mb-2">
                                    <Activity className="w-3 h-3 text-emerald-500" /> Стандартная порция
                                </div>
                                <div className="text-white font-bold text-sm">
                                    {product.standard_serving?.description || `${product.standard_serving?.amount} ${product.standard_serving?.unit}`}
                                </div>
                                {product.standard_serving?.grams && (
                                    <div className="text-[10px] text-neutral-500 font-medium">≈ {product.standard_serving.grams} г</div>
                                )}
                            </div>
                            <div className="bg-white/5 rounded-2xl p-3 border border-white/5">
                                <div className="flex items-center gap-2 text-[10px] text-neutral-500 uppercase font-bold mb-2">
                                    <Info className="w-3 h-3 text-amber-500" /> Энергия
                                </div>
                                <div className="text-white font-bold text-sm">
                                    {Math.round(product.nutrition_per_serving?.energy_kcal || product.nutrition_per_100g?.energy_kcal || 0)} ккал
                                </div>
                                <div className="text-[10px] text-neutral-500 font-medium">на порцию</div>
                            </div>
                        </div>

                        {product.warnings && product.warnings.length > 0 && (
                            <div className="flex flex-wrap gap-2 mb-4">
                                {product.warnings.map((w: string, i: number) => (
                                    <div key={i} className="flex items-center gap-1.5 bg-amber-500/10 border border-amber-500/20 text-amber-200 text-[10px] px-2 py-1 rounded-lg">
                                        <AlertTriangle className="w-3 h-3" />
                                        {w}
                                    </div>
                                ))}
                            </div>
                        )}

                        <div className="flex items-center justify-between pt-4 border-t border-white/5">
                            <div className="flex gap-4">
                                <div className="flex flex-col">
                                    <span className="text-[9px] text-neutral-500 font-bold uppercase tracking-tighter">Белок</span>
                                    <span className="text-xs font-bold text-blue-400">{(product.nutrition_per_serving?.protein_g || product.nutrition_per_100g?.protein_g || 0).toFixed(1)}г</span>
                                </div>
                                <div className="flex flex-col">
                                    <span className="text-[9px] text-neutral-500 font-bold uppercase tracking-tighter">Жиры</span>
                                    <span className="text-xs font-bold text-amber-400">{(product.nutrition_per_serving?.fat_g || product.nutrition_per_100g?.fat_g || 0).toFixed(1)}г</span>
                                </div>
                                <div className="flex flex-col">
                                    <span className="text-[9px] text-neutral-500 font-bold uppercase tracking-tighter">Угли</span>
                                    <span className="text-xs font-bold text-purple-400">{(product.nutrition_per_serving?.carbs_g || product.nutrition_per_100g?.carbs_g || 0).toFixed(1)}г</span>
                                </div>
                            </div>

                            <button
                                onClick={() => {
                                    // Proactive: offer to use this product in Quick Log?
                                    // For now, just a placeholder for "Detailed Info" or "How to Use"
                                }}
                                className="w-8 h-8 bg-white/5 rounded-full flex items-center justify-center hover:bg-emerald-500/20 group-hover:translate-x-1 transition-all"
                            >
                                <ChevronRight className="w-4 h-4 text-neutral-500 group-hover:text-emerald-500" />
                            </button>
                        </div>
                    </div>
                ))}

                {filteredProducts.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-20 text-center">
                        <span className="text-6xl mb-4 grayscale">🧐</span>
                        <h3 className="text-lg font-bold text-white mb-1">Ничего не нашли</h3>
                        <p className="text-neutral-500 text-sm">Попробуйте поискать по-другому или проверьте опечатки.</p>
                    </div>
                )}
            </div>
        </div>
    )
}
