import React from 'react';
import { Home, Users, BotMessageSquare } from 'lucide-react';
import WebAppConfig from '@twa-dev/sdk';

interface CuratorProps {
    user: any;
    onNavigate: (tab: any) => void;
}

export const CuratorDashboard: React.FC<CuratorProps> = ({ onNavigate }) => {
    const handleBotRedirect = () => {
        if (WebAppConfig.initDataUnsafe?.user) {
            WebAppConfig.close();
        } else {
            alert("Пожалуйста, закройте приложение и используйте меню бота.");
        }
    };

    return (
        <div className="pb-24 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center gap-2 mb-6 cursor-pointer" onClick={() => onNavigate('dashboard')}>
                <Home className="w-5 h-5 text-emerald-500" />
                <span className="text-emerald-500 font-medium text-sm">На главную</span>
            </div>

            <div className="flex justify-between items-center mb-6">
                <h2 className="font-semibold text-xl flex items-center gap-2 text-white">
                    <Users className="w-6 h-6 text-purple-400" /> Кабинет Куратора
                </h2>
            </div>

            <div className="bg-gradient-to-br from-neutral-900 to-neutral-800/80 border border-purple-500/20 rounded-3xl p-8 relative overflow-hidden text-center shadow-xl">
                <div className="absolute -top-10 -right-10 w-40 h-40 bg-purple-500/10 blur-[60px] rounded-full pointer-events-none"></div>

                <div className="w-20 h-20 bg-neutral-950 rounded-full flex items-center justify-center mx-auto mb-6 border border-white/5 relative z-10 shadow-lg shadow-purple-500/10">
                    <BotMessageSquare className="w-10 h-10 text-purple-400" />
                </div>

                <h3 className="text-xl font-bold text-white mb-3 relative z-10">Режим Куратора</h3>
                <p className="text-neutral-400 text-sm mb-6 relative z-10 leading-relaxed">
                    Функции куратора (статистика подопечных, рассылки, генерация ссылок и голосовые сообщения) глубоко интегрированы с Telegram.
                    Для безопасности и удобства управления используйте интерфейс бота.
                </p>

                <button
                    onClick={handleBotRedirect}
                    className="w-full relative overflow-hidden group py-4 rounded-2xl font-bold flex items-center justify-center gap-2 transition-all bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white shadow-[0_0_30px_rgba(168,85,247,0.3)] active:scale-95 border border-purple-400/50"
                >
                    <Users className="w-5 h-5 relative z-10" />
                    <span className="relative z-10">Открыть меню в Telegram</span>
                </button>
            </div>
        </div>
    );
};
