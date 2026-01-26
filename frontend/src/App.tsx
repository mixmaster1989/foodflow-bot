import { useState, useEffect } from 'react'
import { Loader2, ShoppingBasket } from 'lucide-react'
import { useAuth } from './hooks/useAuth'
import { fridgeApi, statsApi } from './api/client'
import { Apple, LayoutGrid, PlusCircle, Activity, Trash2, Utensils, Search as SearchIcon, X } from 'lucide-react'
import { AddProductModal } from './components/AddProductModal'
import { ShoppingList } from './components/ShoppingList'
import { ConsumptionHistory } from './components/ConsumptionHistory'
import { searchApi } from './api/client'

function App() {
  const { user, token, isLoading: authLoading, error: authError } = useAuth()
  const [products, setProducts] = useState<any[]>([])
  const [report, setReport] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isHistoryOpen, setIsHistoryOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<'fridge' | 'shopping'>('fridge')

  // Search & Summary State
  const [searchQuery, setSearchQuery] = useState('')
  const [aiSummary, setAiSummary] = useState<string | null>(null)
  const [aiTags, setAiTags] = useState<any[]>([])

  // Fetch Data Function
  const refreshData = async (query?: string) => {
    if (!token) return
    setIsLoading(true)
    try {
      if (query !== undefined || searchQuery) {
        // Search Mode
        const data = await searchApi.fridge(query ?? searchQuery)
        setProducts(data.results || [])
      } else {
        // Regular Mode + AI Summary
        const [searchData, reportData] = await Promise.all([
          searchApi.fridge('', true),
          statsApi.getDailyReport()
        ])
        setProducts(searchData.results || [])
        setAiSummary(searchData.summary)
        setAiTags(searchData.tags || [])
        setReport(reportData)
      }
    } catch (err) {
      console.error('Data fetch error:', err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    refreshData()
  }, [token])

  // Handle Search Input
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery.trim()) {
        refreshData(searchQuery)
      } else if (searchQuery === '') {
        refreshData('')
      }
    }, 500)
    return () => clearTimeout(timer)
  }, [searchQuery])

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить продукт?')) return
    try {
      await fridgeApi.deleteProduct(id)
      refreshData()
    } catch (e) { alert('Ошибка удаления') }
  }

  const handleConsume = async (id: number, currentWeight: number) => {
    const amount = prompt(`Сколько съесть (г)? (Всего: ${currentWeight}г)`, '100')
    if (!amount) return
    try {
      await fridgeApi.consumeProduct(id, { amount: Number(amount), unit: 'grams' })
      refreshData() // Update stats and fridge
    } catch (e) { alert('Ошибка: ' + JSON.stringify(e)) }
  }

  if (authLoading) {
    return (
      <div className="min-h-screen bg-neutral-950 flex flex-col items-center justify-center text-emerald-500">
        <Loader2 className="w-10 h-10 animate-spin mb-4" />
        <p className="text-neutral-400 animate-pulse">Initializing FoodFlow...</p>
      </div>
    )
  }

  if (authError) {
    return (
      <div className="min-h-screen bg-neutral-950 flex flex-col items-center justify-center p-8 text-center text-neutral-200">
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-2xl mb-4">
          <p className="text-red-400 font-medium text-lg">Нет доступа</p>
          <p className="text-neutral-400 text-xs mt-2 font-mono break-all">{authError}</p>
        </div>
        <p className="text-neutral-500 text-sm mb-6">
          Телеграм не передал данные для входа.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="px-8 py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-full transition-colors"
        >
          Обновить
        </button>
        <div className="mt-8">
          <a href="/foodflow/?mock=1" className="text-xs text-neutral-600 underline">Войти в демо-режим</a>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 font-sans p-4 pb-24">
      {/* Header */}
      <header className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-green-400 to-emerald-500 bg-clip-text text-transparent">
            FoodFlow
          </h1>
          <p className="text-neutral-500 text-sm">С возвращением, {user?.first_name || 'Шеф'}!</p>
        </div>
        <div className="w-10 h-10 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
          <Apple className="w-6 h-6" />
        </div>
      </header>

      {activeTab === 'fridge' ? (
        <>
          {/* KBZU Overview */}
          <section
            onClick={() => setIsHistoryOpen(true)}
            className="bg-neutral-900 border border-neutral-800 rounded-3xl p-6 mb-8 relative overflow-hidden group cursor-pointer active:scale-[0.98] transition-all"
          >
            <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 blur-[60px] rounded-full pointer-events-none"></div>

            <div className="flex justify-between items-center mb-4">
              <h2 className="font-semibold text-lg flex items-center gap-2">
                <Activity className="w-5 h-5 text-emerald-500" /> Цели на день
              </h2>
              <span className="text-emerald-500 text-sm font-bold">
                {report && report.calories_goal ? Math.round((report.calories_consumed / report.calories_goal) * 100) : 0}%
              </span>
            </div>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-neutral-400">Калории</span>
                  <span>{Math.round(report?.calories_consumed || 0)} / {report?.calories_goal || 2000} ккал</span>
                </div>
                <div className="h-2 w-full bg-neutral-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-emerald-500 transition-all duration-1000 ease-out shadow-[0_0_15px_rgba(16,185,129,0.4)]"
                    style={{ width: `${Math.min(100, (report && report.calories_goal ? (report.calories_consumed / report.calories_goal) * 100 : 0))}%` }}
                  ></div>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4">
                {[
                  { label: 'Белки', val: report?.protein, goal: report?.protein_goal || 150, color: 'bg-blue-400' },
                  { label: 'Жиры', val: report?.fat, goal: report?.fat_goal || 70, color: 'bg-amber-400' },
                  { label: 'Углев', val: report?.carbs, goal: report?.carb_goal || 250, color: 'bg-purple-400' }
                ].map((p) => (
                  <div key={p.label}>
                    <p className="text-[10px] text-neutral-500 mb-1 font-medium uppercase tracking-wider">{p.label}</p>
                    <div className="h-1.5 w-full bg-neutral-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${p.color} transition-all duration-1000 ease-out`}
                        style={{ width: `${Math.min(100, (p.val || 0) / (p.goal || 100) * 100) || 0}%` }}
                      ></div>
                    </div>
                    <p className="text-[10px] text-neutral-400 mt-1">{Math.round(p.val || 0)}г</p>
                  </div>
                ))}
              </div>
            </div>
            <div className="mt-4 text-[10px] text-center text-neutral-600 uppercase tracking-widest font-bold">Нажми, чтобы увидеть историю</div>
          </section>

          {/* Fridge Section */}
          <section>
            <div className="flex justify-between items-center mb-4">
              <h2 className="font-semibold text-lg flex items-center gap-2">
                <LayoutGrid className="w-5 h-5 text-amber-500" /> Холодильник
              </h2>
              <button
                onClick={() => setIsModalOpen(true)}
                className="text-emerald-500 text-sm font-medium px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full"
              >
                + Добавить
              </button>
            </div>

            {/* AI Tags */}
            {aiTags.length > 0 && !searchQuery && (
              <div className="flex gap-2 mb-4 overflow-x-auto pb-2 no-scrollbar">
                {aiTags.map((tag, idx) => (
                  <button
                    key={idx}
                    onClick={() => setSearchQuery(tag.tag)}
                    className="flex-shrink-0 bg-neutral-900 border border-neutral-800 px-3 py-1.5 rounded-full text-xs flex items-center gap-1.5 hover:border-emerald-500 transition-colors"
                  >
                    <span>{tag.emoji}</span>
                    <span>{tag.tag}</span>
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
                placeholder="Поиск продуктов..."
                className="w-full bg-neutral-900 border border-neutral-800 rounded-2xl pl-11 pr-11 py-3 text-sm focus:outline-none focus:border-emerald-500 transition-all font-medium"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-4 top-1/2 -translate-y-1/2"
                >
                  <X className="w-4 h-4 text-neutral-500" />
                </button>
              )}
            </div>

            {/* AI Summary Card */}
            {aiSummary && !searchQuery && (
              <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-2xl p-4 mb-6 relative group overflow-hidden">
                <div className="absolute top-0 right-0 p-2 opacity-20"><Activity className="w-8 h-8" /></div>
                <p className="text-xs text-emerald-400 font-medium mb-1 uppercase tracking-wider flex items-center gap-1.5">
                  🤖 AI РЕВИЗИЯ
                </p>
                <p className="text-xs text-neutral-400 italic">"{aiSummary}"</p>
              </div>
            )}

            {isLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-16 bg-neutral-900/50 border border-neutral-800 rounded-2xl animate-pulse"></div>
                ))}
              </div>
            ) : products.length > 0 ? (
              <div className="grid grid-cols-1 gap-3">
                {products.map((item) => (
                  <div key={item.id} className="group flex items-center justify-between p-4 bg-neutral-900/50 border border-neutral-800 rounded-2xl hover:border-emerald-500/30 transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-neutral-800 rounded-xl group-hover:bg-emerald-500/10 transition-colors">
                        <Apple className="w-5 h-5 text-neutral-400 group-hover:text-emerald-500 transition-colors" />
                      </div>
                      <div>
                        <h3 className="font-medium text-sm">{item.name}</h3>
                        <p className="text-xs text-neutral-500">{item.weight_g}г • {Math.round(item.calories)} ккал</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleConsume(item.id, item.weight_g || 100)}
                        className="p-2 text-neutral-400 hover:text-emerald-500 bg-neutral-800 rounded-full"
                      >
                        <Utensils className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(item.id)}
                        className="p-2 text-neutral-400 hover:text-red-500 bg-neutral-800 rounded-full"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center bg-neutral-900/30 border border-dashed border-neutral-800 rounded-3xl">
                <p className="text-neutral-500 text-sm">В холодильнике пусто</p>
                <p className="text-xs text-neutral-600 mt-1">Добавьте продукты, чтобы следить за питанием</p>
              </div>
            )}
          </section>
        </>
      ) : (
        <ShoppingList onBought={refreshData} />
      )}

      {/* Bottom Nav */}
      <nav className="fixed bottom-6 left-4 right-4 bg-neutral-900/80 backdrop-blur-2xl border border-neutral-800 rounded-[2rem] py-3 px-8 flex justify-between items-center shadow-[0_20px_50px_rgba(0,0,0,0.5)] z-50">
        <button
          className={`p-2 transition-colors ${activeTab === 'fridge' ? 'text-emerald-500' : 'text-neutral-500'}`}
          onClick={() => setActiveTab('fridge')}
        >
          <LayoutGrid className="w-6 h-6" />
        </button>
        <div className="relative">
          <div className="absolute inset-0 bg-emerald-500 blur-xl opacity-20"></div>
          <button
            className="relative bg-emerald-500 p-4 rounded-full -mt-12 border-[6px] border-neutral-950 shadow-lg active:scale-90 transition-transform hover:bg-emerald-400"
            onClick={() => setIsModalOpen(true)}
          >
            <PlusCircle className="w-7 h-7 text-white" />
          </button>
        </div>
        <button
          className={`p-2 transition-colors ${activeTab === 'shopping' ? 'text-blue-500' : 'text-neutral-500'}`}
          onClick={() => setActiveTab('shopping')}
        >
          <ShoppingBasket className="w-6 h-6" />
        </button>
      </nav>

      {/* Modals */}
      <AddProductModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={refreshData}
      />
      <ConsumptionHistory
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
      />
    </div>
  )
}

export default App
