import { useState, useEffect } from 'react'
import { PlusCircle, Activity, Home } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from './hooks/useAuth'
import { statsApi } from './api/client'
import { AddProductModal } from './components/AddProductModal'
import { ShoppingList } from './components/ShoppingList'
import { ConsumptionHistory } from './components/ConsumptionHistory'
import { QuickLogModal } from './components/QuickLogModal'
import { WaterModal } from './components/WaterModal'
import { Dashboard } from './components/Dashboard'
import { Recipes } from './components/Recipes'
import { Stats } from './components/Stats'
import { Weight } from './components/Weight'
import { Settings } from './components/Settings'
import { Subscriptions } from './components/Subscriptions'
import { Referrals } from './components/Referrals'
import { CuratorDashboard } from './components/CuratorDashboard'
import { AdminPanel } from './components/AdminPanel'
import { Fridge } from './components/Fridge'
import { HerbalifeCatalog } from './components/HerbalifeCatalog'
import { PremiumSplashScreen } from './components/PremiumSplashScreen'
import AIWhisper from './components/AIWhisper'
import { useToast } from './components/Toast'
import { LoginView } from './components/LoginView'
import { WebOnboardingModal } from './components/WebOnboardingModal'
const TierBadge: React.FC<{ tier: string }> = ({ tier }) => {
  if (tier === 'pro') {
    return (
      <div className="flex flex-col items-end mr-2">
        <span className="text-[8px] font-black text-amber-500 uppercase tracking-[0.2em] mb-0.5 animate-pulse">Ultimate</span>
        <span className="text-lg font-black italic text-gold-shimmer animate-pro-glow leading-none">PRO 🚀</span>
      </div>
    );
  }
  if (tier === 'basic') {
    return (
      <div className="flex flex-col items-end mr-2">
        <span className="text-[8px] font-bold text-blue-400 uppercase tracking-widest mb-0.5">Premium</span>
        <span className="text-lg font-bold italic bg-gradient-to-r from-blue-400 to-indigo-500 bg-clip-text text-transparent leading-none drop-shadow-[0_0_10px_rgba(96,165,250,0.5)]">BASIC</span>
      </div>
    );
  }
  if (tier === 'curator') {
    return (
      <div className="flex flex-col items-end mr-2">
        <span className="text-[8px] font-black text-emerald-400 uppercase tracking-[0.3em] mb-0.5 animate-pulse">Master</span>
        <span className="text-lg font-black italic bg-gradient-to-r from-emerald-400 via-teal-500 to-cyan-600 bg-clip-text text-transparent leading-none drop-shadow-[0_0_15px_rgba(52,211,153,0.4)]">CURATOR</span>
      </div>
    );
  }
  return (
    <div className="flex flex-col items-end mr-2 opacity-60">
      <span className="text-[8px] font-medium text-neutral-500 uppercase tracking-tighter mb-0.5">Standard</span>
      <span className="text-lg font-bold text-neutral-400 leading-none">FREE</span>
    </div>
  );
};

function App() {
  const {
    user,
    token,
    isLoading: authLoading,
    error: authError,
    needsLogin,
    loginWithPassword,
    loginWithEmail,
    registerWithEmail,
    isCurator,
    isPro,
    isBasic,
    isFree,
    refreshUser
  } = useAuth()

  const toast = useToast()

  const [report, setReport] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [showSplash, setShowSplash] = useState(true)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isQuickLogOpen, setIsQuickLogOpen] = useState(false)
  const [isWaterOpen, setIsWaterOpen] = useState(false)
  const [isHistoryOpen, setIsHistoryOpen] = useState(false)
  const [historyDate, setHistoryDate] = useState<Date | undefined>(undefined)
  const [activeTab, setActiveTab] = useState<'dashboard' | 'fridge' | 'shopping' | 'recipes' | 'stats' | 'weight' | 'settings' | 'subscriptions' | 'referrals' | 'curator' | 'admin' | 'herbalife' | 'help' | 'contact'>('dashboard')
  const [whisperTrigger, setWhisperTrigger] = useState<{ action: string; detail: string; timestamp: number } | null>(null)
  const [bgUrl, setBgUrl] = useState<string | null>(null)

  // Fetch Data Function (Daily Report & BG)
  const refreshData = async () => {
    if (!token) return
    setIsLoading(true)
    try {
      // Background check
      if (activeTab === 'fridge') {
        setBgUrl(`${import.meta.env.VITE_API_BASE_URL || ''}/api/assets/daily-bg?token=${token}&v=${new Date().getDate()}`)
      }
      const reportData = await statsApi.getDailyReport()
      setReport(reportData)
    } catch (err) {
      console.error('Report fetch error:', err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    refreshData()
  }, [token, activeTab])

  // Force splash screen for at least 5s for "Wow Effect"
  useEffect(() => {
    if (!authLoading) {
      const timer = setTimeout(() => {
        setShowSplash(false)
        setWhisperTrigger({ action: 'greeting', detail: 'User just logged in', timestamp: Date.now() })
      }, 500)
      return () => clearTimeout(timer)
    }
  }, [authLoading])

  // Show diagnostic error if startup failed
  if (authError && !needsLogin) {
    return (
      <div className="min-h-screen bg-neutral-950 flex flex-col items-center justify-center p-8 text-center text-neutral-200">
        <div className="w-20 h-20 bg-red-500/20 rounded-full flex items-center justify-center mb-6 border border-red-500/30">
          <Activity className="w-10 h-10 text-red-500 animate-pulse" />
        </div>
        <h1 className="text-2xl font-bold bg-gradient-to-r from-red-400 to-orange-500 bg-clip-text text-transparent mb-4">
          Ошибка запуска
        </h1>
        <div className="glass-panel p-4 rounded-2xl mb-8 max-w-xs border-red-500/20">
          <p className="text-red-400 font-mono text-[10px] break-all mb-2">DEBUG_INFO: {authError}</p>
          <p className="text-neutral-500 text-[10px]">Браузер: {navigator.userAgent.substring(0, 100)}...</p>
        </div>
        <button
          onClick={() => window.location.reload()}
          className="px-10 py-4 bg-white text-black font-black rounded-full active:scale-90 transition-transform shadow-2xl"
        >
          ПЕРЕЗАГРУЗИТЬ 🔄
        </button>
        <div className="mt-12 text-[9px] text-neutral-700 font-mono">
          Ref: {window.location.hostname} / Path: {window.location.pathname}
        </div>
      </div>
    )
  }

  if (needsLogin) {
    return <LoginView
      onLogin={loginWithPassword}
      onLoginEmail={loginWithEmail}
      onRegister={registerWithEmail}
    />
  }

  // Guard access to settings to prevent crashes
  const needsOnboarding = user && user.settings?.is_initialized === false

  if (needsOnboarding) {
    return <WebOnboardingModal onComplete={refreshUser} />
  }

  return (
    <AnimatePresence mode="wait">
      {showSplash ? (
        <PremiumSplashScreen key="splash" tier={isCurator ? 'curator' : isPro ? 'pro' : isBasic ? 'basic' : 'free'} />
      ) : (
        <motion.div
          key="main"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="min-h-screen text-neutral-100 font-sans p-4 pb-24 relative overflow-x-hidden"
        >
          <AIWhisper trigger={whisperTrigger} onComplete={() => setWhisperTrigger(null)} />

          <div className="dynamic-bg">
            {bgUrl && <img src={bgUrl} alt="" className={isLoading ? 'opacity-0' : 'opacity-40'} />}
          </div>

          <header className="flex items-center justify-between mb-8 relative z-10">
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-green-400 to-emerald-500 bg-clip-text text-transparent">FoodFlow</h1>
              <p className="text-neutral-500 text-sm">С возвращением, {user?.first_name || 'Шеф'}!</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-right">
                <p className="text-[10px] text-neutral-500 font-bold uppercase tracking-widest leading-none mb-1">Ваш статус</p>
                <TierBadge tier={isCurator ? 'curator' : isPro ? 'pro' : isBasic ? 'basic' : 'free'} />
              </div>
              <div className="w-12 h-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center group overflow-hidden shadow-xl backdrop-blur-md">
                <img
                  src={`logos/${isCurator ? 'curator' : isPro ? 'pro' : isBasic ? 'basic' : 'free'}.png`}
                  alt="Tier"
                  className="w-10 h-10 object-contain transition-transform group-hover:scale-110 duration-500"
                />
              </div>
            </div>
          </header>

          <main className="max-w-2xl mx-auto space-y-6">
            {activeTab === 'dashboard' && (
              <Dashboard
                user={user}
                report={report}
                onNavigate={setActiveTab}
                onOpenQuickLog={() => setIsQuickLogOpen(true)}
                onOpenWater={() => setIsWaterOpen(true)}
                onOpenHistory={() => setIsHistoryOpen(true)}
              />
            )}
            {activeTab === 'fridge' && <Fridge user={user} onNavigate={setActiveTab} onRefresh={refreshData} />}
            {activeTab === 'shopping' && (
              <>
                <div className="flex items-center gap-2 mb-6 cursor-pointer" onClick={() => setActiveTab('dashboard')}>
                  <Home className="w-5 h-5 text-blue-500" />
                  <span className="text-blue-500 font-medium text-sm">На главную</span>
                </div>
                <ShoppingList onBought={refreshData} />
              </>
            )}
            {activeTab === 'recipes' && <Recipes onNavigate={setActiveTab} />}
            {activeTab === 'stats' && <Stats onNavigate={setActiveTab} onOpenHistory={() => { setIsHistoryOpen(true); }} />}
            {activeTab === 'weight' && <Weight user={user} onNavigate={setActiveTab} />}
            {activeTab === 'settings' && <Settings user={user} onNavigate={setActiveTab} />}
            {activeTab === 'subscriptions' && <Subscriptions user={user} onNavigate={setActiveTab} />}
            {activeTab === 'referrals' && <Referrals user={user} onNavigate={setActiveTab} />}
            {activeTab === 'curator' && <CuratorDashboard user={user} onNavigate={setActiveTab} />}
            {activeTab === 'admin' && <AdminPanel user={user} onNavigate={setActiveTab} />}
            {activeTab === 'herbalife' && <HerbalifeCatalog />}
            {activeTab === 'help' && (
              <div className="glass-panel p-6 rounded-3xl">
                <h2 className="text-xl font-bold mb-4">Помощь и поддержка</h2>
                <div className="space-y-4">
                  <p className="text-neutral-300">Наш бот всегда поможет вам с вопросами питания.</p>
                  <a href="https://t.me/FoodFlow2026bot" target="_blank" className="block p-4 bg-neutral-800 rounded-2xl hover:bg-neutral-700 transition-colors">Написать в поддержку</a>
                </div>
              </div>
            )}
          </main>

          <footer className="fixed bottom-6 left-4 right-4 bg-neutral-900/80 backdrop-blur-2xl border border-neutral-800 rounded-[2rem] py-3 px-8 flex justify-between items-center shadow-[0_20px_50px_rgba(0,0,0,0.5)] z-50">
            <button className={`p-2 transition-colors ${activeTab === 'dashboard' ? 'text-emerald-500' : 'text-neutral-500'}`} onClick={() => setActiveTab('dashboard')}>
              <Home className="w-6 h-6" />
            </button>
            <button
              className={`p-2 transition-colors ${activeTab === 'fridge' ? 'text-emerald-500' : 'text-neutral-500'} ${isFree ? 'opacity-30' : ''}`}
              onClick={() => {
                if (isFree) { toast.info('Умный Холодильник доступен в тарифе Basic и выше'); return; }
                setActiveTab('fridge');
              }}
            >
              <div className="relative">
                <div className="w-6 h-6 flex items-center justify-center">🧊</div>
                {isFree && <div className="absolute -top-1 -right-1 text-[8px]">🔒</div>}
              </div>
            </button>
            <button
              onClick={() => {
                if (isFree) { setActiveTab('subscriptions'); return; }
                setActiveTab('recipes');
              }}
              className={`p-2 transition-colors ${activeTab === 'recipes' ? 'text-emerald-500' : 'text-neutral-500'} ${isFree ? 'opacity-30' : ''}`}
            >
              <div className="relative">
                <div className="w-6 h-6 flex items-center justify-center">👨‍🍳</div>
                {isFree && <div className="absolute -top-1 -right-1 text-[8px]">🔒</div>}
              </div>
            </button>
            <div className="relative">
              <div className="absolute inset-0 bg-emerald-500 blur-xl opacity-20"></div>
              <button className="relative bg-emerald-500 p-4 rounded-full -mt-12 border-[6px] border-neutral-950 shadow-lg active:scale-90 transition-transform hover:bg-emerald-400" onClick={() => setIsModalOpen(true)}>
                <PlusCircle className="w-7 h-7 text-white" />
              </button>
            </div>
            <button
              onClick={() => {
                if (isFree) { setActiveTab('subscriptions'); return; }
                setActiveTab('stats');
              }}
              className={`p-2 transition-colors ${activeTab === 'stats' ? 'text-emerald-500' : 'text-neutral-500'} ${isFree ? 'opacity-30' : ''}`}
            >
              <div className="relative">
                <div className="w-6 h-6 flex items-center justify-center">📊</div>
                {isFree && <div className="absolute -top-1 -right-1 text-[8px]">🔒</div>}
              </div>
            </button>
            <div className="relative">
              <div className="absolute inset-0 bg-blue-500 blur-xl opacity-20"></div>
              <button
                className={`relative z-10 p-3 rounded-full border transition-all active:scale-95 ${isHistoryOpen ? 'bg-blue-500 text-white border-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.5)]' : 'bg-neutral-800 text-neutral-400 border-neutral-700 hover:text-white hover:border-blue-500'}`}
                onClick={() => setIsHistoryOpen(!isHistoryOpen)}
              >
                <Activity className="w-5 h-5" />
              </button>
            </div>
          </footer>

          <div className="fixed bottom-24 right-6 z-40 flex flex-col gap-3">
            <button onClick={() => setIsWaterOpen(true)} className="p-4 bg-blue-600 hover:bg-blue-500 text-white rounded-full shadow-lg shadow-blue-500/30 transform hover:scale-110 active:scale-95 transition-all">💧</button>
            <button onClick={() => setIsQuickLogOpen(true)} className="p-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded-full shadow-lg shadow-emerald-500/30 transform hover:scale-110 active:scale-95 transition-all">⚡</button>
          </div>

          <QuickLogModal isOpen={isQuickLogOpen} onClose={() => setIsQuickLogOpen(false)} onSuccess={refreshData} />
          <AddProductModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} onSuccess={refreshData} />
          <ConsumptionHistory isOpen={isHistoryOpen} onClose={() => { setIsHistoryOpen(false); setHistoryDate(undefined); }} targetDate={historyDate} />
          <WaterModal isOpen={isWaterOpen} onClose={() => setIsWaterOpen(false)} onSuccess={refreshData} />
        </motion.div>
      )}
    </AnimatePresence>
  )
}


export default App
