import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface AIWhisperProps {
    trigger: { action: string; detail: string; timestamp: number } | null;
    onComplete?: () => void;
}

const AIWhisper: React.FC<AIWhisperProps> = ({ trigger, onComplete }) => {
    const [text, setText] = useState('');
    const [isVisible, setIsVisible] = useState(false);
    const streamRef = useRef<ReadableStreamDefaultReader | null>(null);

    useEffect(() => {
        const handleGlobalWhisper = (e: any) => {
            const { action, detail } = e.detail;
            startStreaming(action, detail);
        };

        window.addEventListener('ff-whisper', handleGlobalWhisper);
        return () => window.removeEventListener('ff-whisper', handleGlobalWhisper);
    }, []);

    const startStreaming = async (action: string, detail: string) => {
        if (streamRef.current) {
            await streamRef.current.cancel();
        }

        setText('');
        setIsVisible(true);

        const token = localStorage.getItem('ff_token');
        const url = `/api/ai/insight?action=${encodeURIComponent(action)}&detail=${encodeURIComponent(detail)}`;

        try {
            const response = await fetch(url, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.body) return;

            const reader = response.body.getReader();
            streamRef.current = reader;
            const decoder = new TextDecoder();

            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');

                // Keep the last partial line in the buffer
                buffer = lines.pop() || '';

                for (const line of lines) {
                    const trimmed = line.trim();
                    if (trimmed.startsWith('data: ')) {
                        const content = trimmed.substring(6);
                        if (content) {
                            setText((prev) => prev + content);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('AI Whisper stream error:', error);
            setIsVisible(false);
        } finally {
            setTimeout(() => {
                setIsVisible(false);
                if (onComplete) onComplete();
            }, 7000); // Slightly longer for readability
        }
    };

    useEffect(() => {
        if (trigger) {
            startStreaming(trigger.action, trigger.detail);
        }
    }, [trigger]);

    return (
        <AnimatePresence>
            {isVisible && (
                <motion.div
                    initial={{ opacity: 0, y: -20, filter: 'blur(10px)' }}
                    animate={{ opacity: 0.6, y: 0, filter: 'blur(0px)' }}
                    exit={{ opacity: 0, scale: 0.95, filter: 'blur(10px)' }}
                    className="fixed top-20 left-0 right-0 z-[9999] flex justify-center pointer-events-none px-6"
                >
                    <div className="max-w-md text-center">
                        <motion.p
                            className="text-white font-light italic tracking-wide drop-shadow-[0_0_8px_rgba(255,255,255,0.5)] text-lg"
                            style={{ fontFamily: "'Inter', sans-serif" }}
                        >
                            {text}
                            <motion.span
                                animate={{ opacity: [0, 1, 0] }}
                                transition={{ duration: 0.8, repeat: Infinity }}
                                className="inline-block w-1 h-5 bg-white/50 ml-1 align-middle"
                            />
                        </motion.p>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
};

export default AIWhisper;
