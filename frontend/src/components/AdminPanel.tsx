import React from 'react';
import { Home, Shield, AlertTriangle, Terminal } from 'lucide-react';
import WebAppConfig from '@twa-dev/sdk';

interface AdminProps {
    user: any;
    onNavigate: (tab: any) => void;
}

export const AdminPanel: React.FC<AdminProps> = ({ onNavigate }) => {
    const handleBotRedirect = () => {
        if (WebAppConfig.initDataUnsafe?.user) {
            WebAppConfig.close();
        } else {
            alert("Пожалуйста, закройте приложение и используйте меню администратора в боте.");
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
                    <Shield className="w-6 h-6 text-red-500" /> Админ-Панель
                </h2>
            </div>

            <div className="bg-gradient-to-br from-neutral-900 to-neutral-800/80 border border-red-500/20 rounded-3xl p-8 relative overflow-hidden text-center shadow-xl mb-6">
                <div className="absolute -top-10 -right-10 w-40 h-40 bg-red-500/10 blur-[60px] rounded-full pointer-events-none"></div>

                <div className="w-20 h-20 bg-neutral-950 rounded-full flex items-center justify-center mx-auto mb-6 border border-white/5 relative z-10 shadow-lg shadow-red-500/10">
                    <Terminal className="w-10 h-10 text-red-500" />
                </div>

                <h3 className="text-xl font-bold text-white mb-3 relative z-10">Доступ Администратора</h3>
                <p className="text-neutral-400 text-sm mb-6 relative z-10 leading-relaxed">
                    Управление ботом, перезапуск сервисов (RESTART), глобальные рассылки и просмотр баланса Stars выполняются исключительно через защищенный интерфейс Telegram-бота.
                </p>

                <button
                    onClick={handleBotRedirect}
                    className="w-full relative overflow-hidden group py-4 rounded-2xl font-bold flex items-center justify-center gap-2 transition-all bg-gradient-to-r from-red-600 to-orange-600 hover:from-red-500 hover:to-orange-500 text-white shadow-[0_0_30px_rgba(239,68,68,0.3)] active:scale-95 border border-red-400/50"
                >
                    <Shield className="w-5 h-5 relative z-10" />
                    <span className="relative z-10">В меню администратора</span>
                </button>
            </div>

            <div className="flex items-start gap-2 text-xs text-neutral-500 bg-neutral-900/50 p-4 rounded-2xl border border-white/5">
                <AlertTriangle className="w-4 h-4 flex-shrink-0 text-red-400/50" />
                <span>
                    Данный раздел доступен только по Telegram ID, внесенным в `config.ADMIN_IDS`. Убедитесь, что ваш ID находится в списке.
                </span>
            </div>
        </div>
    );
};
