import React, { useEffect, useRef, useState } from 'react'
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion'
import confetti from 'canvas-confetti'

const LOADING_MESSAGES = [
    "Инициализация AI...",
    "Загрузка нутриентов...",
    "Анализ рациона...",
    "Синхронизация профиля...",
    "Подготовка меню...",
    "Финальная настройка..."
]

interface SplashProps {
    tier: string
}

export const PremiumSplashScreen: React.FC<SplashProps> = ({ tier }) => {
    const [msgIndex, setMsgIndex] = useState(0)
    const containerRef = useRef<HTMLDivElement>(null)

    // Dynamic Color Palette
    const colors = {
        pro: { glow: '#fbbf24', secondary: '#f59e0b', text: 'text-amber-500/80', confetti: ['#fbbf24', '#f59e0b', '#ffffff'] },
        basic: { glow: '#60a5fa', secondary: '#3b82f6', text: 'text-blue-500/80', confetti: ['#60a5fa', '#3b82f6', '#ffffff'] },
        free: { glow: '#a3e635', secondary: '#84cc16', text: 'text-lime-500/80', confetti: ['#a3e635', '#84cc16', '#ffffff'] },
        curator: { glow: '#34d399', secondary: '#0d9488', text: 'text-emerald-400/80', confetti: ['#34d399', '#0d9488', '#ffffff'] }
    }[tier as 'pro' | 'basic' | 'free' | 'curator'] || { glow: '#10b981', secondary: '#059669', text: 'text-emerald-500/80', confetti: ['#10b981', '#ffffff'] }

    // Parallax effect values
    const mouseX = useMotionValue(0)
    const mouseY = useMotionValue(0)

    const springConfig = { stiffness: 150, damping: 20 }
    const rotateX = useSpring(useTransform(mouseY, [-0.5, 0.5], [10, -10]), springConfig)
    const rotateY = useSpring(useTransform(mouseX, [-0.5, 0.5], [-10, 10]), springConfig)

    useEffect(() => {
        // Init TG WebApp
        const tg = (window as any).Telegram?.WebApp
        if (tg) {
            tg.ready()
            tg.expand()
        }

        const handleMouseMove = (e: MouseEvent) => {
            const { clientX, clientY } = e
            const { innerWidth, innerHeight } = window
            mouseX.set(clientX / innerWidth - 0.5)
            mouseY.set(clientY / innerHeight - 0.5)
        }

        const handleOrientation = (e: DeviceOrientationEvent) => {
            if (e.beta !== null && e.gamma !== null) {
                // gamma: left to right [-90, 90]
                // beta: front to back [-180, 180]
                // We normalize these for the same parallax effect as mouse
                mouseX.set(e.gamma / 45) // More sensitivity
                mouseY.set(e.beta / 45)
            }
        }

        window.addEventListener('mousemove', handleMouseMove)
        window.addEventListener('deviceorientation', handleOrientation)

        // TG Haptics - delayed for reliability
        const hapticTimer = setTimeout(() => {
            if (tg?.HapticFeedback) {
                tg.HapticFeedback.impactOccurred('heavy')
            }
        }, 150)

        // 1. МГНОВЕННЫЙ МАССИВНЫЙ ВЗРЫВ
        confetti({
            particleCount: 400,
            spread: 360,
            startVelocity: 25,
            origin: { x: 0.5, y: 0.5 },
            colors: colors.confetti,
            gravity: 0.4,
            scalar: 0.8,
            zIndex: 101
        });

        // Loop through messages
        const msgTimer = setInterval(() => {
            setMsgIndex(prev => (prev + 1) % LOADING_MESSAGES.length)
        }, 1000)

        // 2. ДОПОЛНИТЕЛЬНЫЕ ЗАЛПЫ
        const burstInterval = setInterval(() => {
            confetti({
                particleCount: 40,
                angle: Math.random() * 360,
                spread: 120,
                origin: { x: 0.5, y: 0.4 },
                colors: [colors.glow, colors.secondary],
                gravity: 0.4,
                scalar: 0.6
            });
        }, 600);

        const stopBurstTimer = setTimeout(() => clearInterval(burstInterval), 5000);

        return () => {
            window.removeEventListener('mousemove', handleMouseMove)
            window.removeEventListener('deviceorientation', handleOrientation)
            clearInterval(msgTimer)
            clearInterval(burstInterval)
            clearTimeout(stopBurstTimer)
            clearTimeout(hapticTimer)
        };
    }, [tier])

    return (
        <motion.div
            ref={containerRef}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, scale: 1.05 }}
            transition={{ duration: 0.8, ease: "easeInOut" }}
            className="fixed inset-0 z-[100] bg-neutral-950 flex flex-col items-center justify-center overflow-hidden"
        >
            <style>
                {`
                @keyframes neon-flicker {
                    0%, 30%, 60%, 90%, 100% {
                        opacity: 1;
                        filter: drop-shadow(0 0 20px ${colors.glow}cc) drop-shadow(0 0 40px ${colors.glow}66);
                    }
                    15%, 45%, 75% {
                        opacity: 0.5;
                        filter: drop-shadow(0 0 10px ${colors.glow}4d);
                    }
                }
                .neon-logo {
                    animation: neon-flicker 8s infinite;
                }
                `}
            </style>

            {/* Мягкий фоновый свет */}
            <div
                className="absolute inset-0"
                style={{ background: `radial-gradient(circle_at_50%_50%, ${colors.glow}14 0%, transparent 70%)` }}
            />

            <motion.div
                style={{ rotateX, rotateY, transformStyle: "preserve-3d" }}
                className="relative flex flex-col items-center z-10"
            >
                {/* Логотип */}
                <div className="relative mb-8" style={{ transform: "translateZ(50px)" }}>
                    <motion.div
                        initial={{ scale: 0.8, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={{
                            type: "spring",
                            stiffness: 100,
                            damping: 15,
                            delay: 0.1
                        }}
                        className="relative w-64 h-64 flex items-center justify-center"
                    >
                        <img
                            src={`/logos/${tier}.png`}
                            alt="Logo"
                            className="w-full h-full object-contain neon-logo"
                        />
                    </motion.div>
                </div>

                {/* Название */}
                <div className="flex flex-col items-center" style={{ transform: "translateZ(30px)" }}>
                    <motion.h1
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.5 }}
                        className="text-5xl font-black tracking-tight text-white mb-2"
                    >
                        FoodFlow
                    </motion.h1>

                    <motion.p
                        key={msgIndex}
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 0.2 }}
                        className={`${colors.text} text-[10px] tracking-[0.4em] uppercase font-black h-4 text-center`}
                    >
                        {LOADING_MESSAGES[msgIndex]}
                    </motion.p>
                </div>
            </motion.div>

            {/* Элегантная линия загрузки */}
            <div className="absolute bottom-20 left-1/2 -translate-x-1/2 w-64 h-1 bg-white/5 rounded-full overflow-hidden">
                <motion.div
                    initial={{ x: "-100%" }}
                    animate={{ x: "100%" }}
                    transition={{
                        duration: 3,
                        repeat: Infinity,
                        ease: "linear"
                    }}
                    style={{ background: `linear-gradient(to right, transparent, ${colors.glow}, transparent)` }}
                    className="w-full h-full"
                />
            </div>
        </motion.div>
    )
}
