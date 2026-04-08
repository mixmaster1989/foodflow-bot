import { useState, useEffect } from 'react';
import {
    LayoutGrid,
    Search as SearchIcon,
    X,
    Activity,
    Apple,
    Utensils,
    Trash2,
    Camera,
    FileText,
    TrendingDown,
    Loader2,
    Home
} from 'lucide-react';
import { fridgeApi, receiptsApi, searchApi } from '../api/client';
import ReceiptReviewModal from './ReceiptReviewModal';

interface FridgeProps {
    user: any;
    onNavigate: (tab: any) => void;
    onRefresh: () => void;
}

export const Fridge: React.FC<FridgeProps> = ({ onNavigate, onRefresh }) => {
    const [products, setProducts] = useState<any[]>([]);
    const [summary, setSummary] = useState<any>(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [aiSummary, setAiSummary] = useState<string | null>(null);
    const [aiTags, setAiTags] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isScanning, setIsScanning] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [scannedReceipt, setScannedReceipt] = useState<{ id: number; items: any[]; total: number } | null>(null);

    const fetchFridgeData = async (query?: string) => {
        setIsLoading(true);
        setError(null);
        try {
            // 1. Fetch Summary
            const summaryData = await fridgeApi.getSummary();
            setSummary(summaryData);

            // 2. Fetch Products (Using searchApi for AI features if no query, or fridgeApi if search)
            if (query || searchQuery) {
                const data = await fridgeApi.getProducts({ query: query || searchQuery });
                setProducts(data.items || []);
                // Hide AI summary/tags when searching
                setAiSummary(null);
                setAiTags([]);
            } else {
                // Use searchApi.fridge('', true) to get AI summary and tags
                const data = await searchApi.fridge('', true);
                setProducts(data.results || []);
                setAiSummary(data.summary);
                setAiTags(data.tags || []);
            }
        } catch (err) {
            console.error('Fridge fetch error:', err);
            setError('Ошибка загрузки холодильника');
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchFridgeData();
    }, []);

    // Debounced search
    useEffect(() => {
        const timer = setTimeout(() => {
            fetchFridgeData(searchQuery);
        }, 500);
        return () => clearTimeout(timer);
    }, [searchQuery]);

    const handleDelete = async (id: number) => {
        if (!confirm('Удалить продукт?')) return;
        try {
            await fridgeApi.deleteProduct(id);
            fetchFridgeData();
            onRefresh(); // Update main dashboard if needed
        } catch (e) {
            alert('Ошибка удаления');
        }
    };

    const handleConsume = async (id: number, currentWeight: number) => {
        const amount = prompt(`Сколько съесть (г)? (Всего: ${currentWeight}г)`, '100');
        if (!amount) return;
        try {
            await fridgeApi.consumeProduct(id, { amount: Number(amount), unit: 'grams' });
            fetchFridgeData();
            onRefresh();
        } catch (e) {
            alert('Ошибка: ' + JSON.stringify(e));
        }
    };

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>, type: 'receipt' | 'label') => {
        const file = e.target.files?.[0];
        if (!file) return;

        setIsScanning(true);
        setError(null);
        try {
            if (type === 'receipt') {
                const result = await receiptsApi.upload(file);
                setScannedReceipt({
                    id: result.receipt_id,
                    items: result.items,
                    total: result.total
                });
            } else {
                const result = await fridgeApi.scanLabel(file);
                // Show a confirmation prompt or auto-add
                if (confirm(`Распознан продукт: ${result.name} (${result.calories} ккал). Добавить в холодильник?`)) {
                    await fridgeApi.addProduct({
                        name: result.name,
                        calories: result.calories,
                        protein: result.protein,
                        fat: result.fat,
                        carbs: result.carbs,
                        fiber: result.fiber,
                        weight_g: 100, // Default
                        source: 'label_scan'
                    });
                }
            }
            fetchFridgeData();
        } catch (err) {
            console.error(`${type} scan error:`, err);
            setError(`Ошибка сканирования ${type === 'receipt' ? 'чека' : 'этикетки'}`);
        } finally {
            setIsScanning(false);
        }
    };

    return (
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-700">
            <div className="flex items-center gap-2 mb-6 cursor-pointer group" onClick={() => onNavigate('dashboard')}>
                <Home className="w-5 h-5 text-emerald-500 group-hover:-translate-x-1 transition-transform" />
                <span className="text-emerald-500 font-medium text-sm">На главную</span>
            </div>

            {/* Fridge Header & Summary */}
            <section className="mb-8">
                <div className="flex justify-between items-end mb-6">
                    <div>
                        <h2 className="font-bold text-2xl flex items-center gap-2 mb-1">
                            <LayoutGrid className="w-6 h-6 text-amber-500" /> Холодильник
                        </h2>
                        <p className="text-neutral-500 text-xs font-medium uppercase tracking-widest">Твои запасы (Pro)</p>
                    </div>

                    {summary && (
                        <div className="text-right">
                            <div className="flex items-center gap-2 justify-end text-emerald-400 font-bold text-xl">
                                <Activity className="w-5 h-5" />
                                <span>{Math.round(summary.total_calories)}</span>
                                <span className="text-[10px] text-neutral-500 font-medium uppercase">ккал</span>
                            </div>
                            <p className="text-[10px] text-neutral-500 uppercase tracking-tighter">Всего {summary.total_items} позиций</p>
                        </div>
                    )}
                </div>

                {/* Action Buttons (Bot Parity) */}
                <div className="grid grid-cols-2 gap-3 mb-6">
                    <label className="relative flex flex-col items-center justify-center p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl hover:bg-emerald-500/20 transition-all cursor-pointer group overflow-hidden active:scale-95">
                        <input type="file" accept="image/*" className="hidden" onChange={(e) => handleFileUpload(e, 'receipt')} disabled={isScanning} />
                        <FileText className="w-6 h-6 text-emerald-500 mb-2 group-hover:scale-110 transition-transform" />
                        <span className="text-xs font-bold text-emerald-400 uppercase tracking-tight">Загрузить Чек</span>
                        <div className="absolute -bottom-1 -right-1 opacity-10 group-hover:opacity-20 transition-opacity">
                            <TrendingDown className="w-12 h-12" />
                        </div>
                    </label>

                    <label className="relative flex flex-col items-center justify-center p-4 bg-amber-500/10 border border-amber-500/20 rounded-2xl hover:bg-amber-500/20 transition-all cursor-pointer group overflow-hidden active:scale-95">
                        <input type="file" accept="image/*" className="hidden" onChange={(e) => handleFileUpload(e, 'label')} disabled={isScanning} />
                        <Camera className="w-6 h-6 text-amber-500 mb-2 group-hover:scale-110 transition-transform" />
                        <span className="text-xs font-bold text-amber-400 uppercase tracking-tight">Этикетка</span>
                        <div className="absolute -bottom-1 -right-1 opacity-10 group-hover:opacity-20 transition-opacity">
                            <Activity className="w-12 h-12" />
                        </div>
                    </label>
                </div>

                {/* AI Tags */}
                {aiTags.length > 0 && !searchQuery && (
                    <div className="flex gap-2 mb-6 overflow-x-auto pb-2 no-scrollbar">
                        {aiTags.map((tag, idx) => (
                            <button
                                key={idx}
                                onClick={() => setSearchQuery(tag.tag)}
                                className="flex-shrink-0 bg-neutral-900/60 backdrop-blur-md border border-white/5 px-4 py-2 rounded-full text-xs flex items-center gap-2 hover:border-emerald-500/50 hover:bg-emerald-500/5 transition-all active:scale-95"
                            >
                                <span>{tag.emoji}</span>
                                <span className="font-medium text-neutral-300">{tag.tag}</span>
                            </button>
                        ))}
                    </div>
                )}

                {/* Search Bar */}
                <div className="relative mb-6">
                    <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500" />
                    <input
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Поиск в холодильнике..."
                        className="w-full bg-neutral-900/40 backdrop-blur-xl border border-white/5 rounded-2xl pl-11 pr-11 py-4 text-sm focus:outline-none focus:border-emerald-500/50 transition-all font-medium placeholder:text-neutral-600 shadow-inner"
                    />
                    {searchQuery && (
                        <button
                            onClick={() => setSearchQuery('')}
                            className="absolute right-4 top-1/2 -translate-y-1/2 p-1 hover:bg-white/5 rounded-full transition-colors"
                        >
                            <X className="w-4 h-4 text-neutral-500" />
                        </button>
                    )}
                </div>

                {/* AI Summary Card */}
                {aiSummary && !searchQuery && (
                    <div className="bg-gradient-to-br from-emerald-500/10 to-transparent border border-emerald-500/20 rounded-3xl p-5 mb-8 relative group overflow-hidden shadow-lg shadow-emerald-500/5">
                        <div className="absolute -top-4 -right-4 p-2 opacity-5 scale-150 rotate-12 group-hover:rotate-0 transition-transform duration-1000">
                            <Activity className="w-24 h-24" />
                        </div>
                        <div className="flex items-center gap-2 mb-3">
                            <div className="p-1.5 bg-emerald-500 rounded-lg shadow-[0_0_10px_rgba(16,185,129,0.5)]">
                                <Loader2 className={`w-3 h-3 text-white ${isLoading ? 'animate-spin' : ''}`} />
                            </div>
                            <p className="text-[10px] text-emerald-400 font-black uppercase tracking-[0.2em]">
                                AI РЕВИЗИЯ
                            </p>
                        </div>
                        <p className="text-sm text-neutral-300 leading-relaxed italic">"{aiSummary}"</p>
                    </div>
                )}

                {/* Products List */}
                <div className="space-y-3">
                    {isLoading && products.length === 0 ? (
                        <div className="space-y-3">
                            {[1, 2, 3, 4].map(i => (
                                <div key={i} className="h-20 bg-neutral-900/50 border border-white/5 rounded-3xl animate-pulse"></div>
                            ))}
                        </div>
                    ) : products.length > 0 ? (
                        products.map((item) => (
                            <div
                                key={item.id}
                                className="group flex items-center justify-between p-4 bg-neutral-900/40 backdrop-blur-md border border-white/5 rounded-3xl hover:border-emerald-500/20 hover:bg-neutral-900/60 transition-all shadow-sm relative overflow-hidden active:scale-[0.98]"
                            >
                                <div className="flex items-center gap-4 relative z-10">
                                    <div className="w-14 h-14 rounded-2xl bg-neutral-950 border border-white/5 flex items-center justify-center group-hover:border-emerald-500/30 transition-all overflow-hidden relative shadow-inner">
                                        <img
                                            src={`${import.meta.env.VITE_API_BASE_URL || ''}/api/assets/icon/${encodeURIComponent(item.name)}?token=${localStorage.getItem('ff_token')}`}
                                            className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-all group-hover:scale-110 duration-500"
                                            alt={item.name}
                                            onError={(e: any) => {
                                                e.target.style.display = 'none';
                                                e.target.nextSibling.style.display = 'block';
                                            }}
                                        />
                                        <Apple className="w-6 h-6 text-neutral-700 absolute hidden" />
                                    </div>
                                    <div>
                                        <h3 className="font-bold text-sm text-neutral-100 group-hover:text-emerald-400 transition-colors uppercase tracking-tight">{item.name}</h3>
                                        <div className="flex items-center gap-1.5 mt-1">
                                            <span className="px-2 py-0.5 bg-white/5 rounded-md text-[9px] font-black text-neutral-500 uppercase tracking-wider">{item.weight_g || 100}г</span>
                                            <span className="w-1 h-1 rounded-full bg-neutral-700"></span>
                                            <span className="text-[10px] text-emerald-500/80 font-bold">{Math.round(item.calories)} ккал</span>
                                        </div>
                                    </div>
                                </div>

                                <div className="flex items-center gap-2 relative z-10 transition-transform group-hover:translate-x-0 translate-x-1 opacity-80 group-hover:opacity-100">
                                    <button
                                        onClick={() => handleConsume(item.id, item.weight_g || 100)}
                                        className="p-3 text-neutral-400 hover:text-emerald-500 bg-white/5 hover:bg-emerald-500/10 rounded-2xl transition-all active:scale-90"
                                        title="Съесть"
                                    >
                                        <Utensils className="w-4 h-4" />
                                    </button>
                                    <button
                                        onClick={() => handleDelete(item.id)}
                                        className="p-3 text-neutral-400 hover:text-red-400 bg-white/5 hover:bg-red-500/10 rounded-2xl transition-all active:scale-90"
                                        title="Удалить"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>

                                {/* Micro-glow on hover */}
                                <div className="absolute top-0 left-0 w-1 h-full bg-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                            </div>
                        ))
                    ) : (
                        <div className="p-12 text-center bg-neutral-900/20 border-2 border-dashed border-white/5 rounded-[2.5rem] mt-4">
                            <div className="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mx-auto mb-4 opacity-50">
                                <LayoutGrid className="w-8 h-8 text-neutral-500" />
                            </div>
                            <h3 className="text-neutral-300 font-bold mb-1">Холодильник пуст</h3>
                            <p className="text-xs text-neutral-500 max-w-[200px] mx-auto leading-relaxed">Загрузи чек или отсканируй этикетку, чтобы наполнить его!</p>
                        </div>
                    )}
                </div>
            </section>

            {/* Floating status for scanning */}
            {isScanning && (
                <div className="fixed inset-x-8 bottom-32 bg-amber-500 text-black p-4 rounded-2xl flex items-center gap-3 shadow-2xl animate-bounce z-[60] font-bold text-sm">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Распознаю продукт... Подожди секунду 🤖</span>
                </div>
            )}

            {error && (
                <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-2xl mb-8 flex items-center gap-3 text-red-400 text-sm animate-shake">
                    <Activity className="w-5 h-5" />
                    <span>{error}</span>
                </div>
            )}

            {scannedReceipt && (
                <ReceiptReviewModal
                    receiptId={scannedReceipt.id}
                    items={scannedReceipt.items}
                    total={scannedReceipt.total}
                    onClose={() => setScannedReceipt(null)}
                    onFinished={() => {
                        setScannedReceipt(null);
                        fetchFridgeData();
                        onRefresh();
                    }}
                />
            )}
        </div>
    );
};
