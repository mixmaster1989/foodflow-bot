import { useRef, useEffect, useState } from 'react';
import { Camera, X, RefreshCcw } from 'lucide-react';

interface CameraOverlayProps {
    onCapture: (blob: Blob) => void;
    onClose: () => void;
}

export function CameraOverlay({ onCapture, onClose }: CameraOverlayProps) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [stream, setStream] = useState<MediaStream | null>(null);
    const [facingMode, setFacingMode] = useState<'user' | 'environment'>('environment');

    const startCamera = async (mode: 'user' | 'environment') => {
        if (stream) {
            stream.getTracks().forEach(t => t.stop());
        }
        try {
            const newStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: mode }
            });
            setStream(newStream);
            if (videoRef.current) {
                videoRef.current.srcObject = newStream;
            }
        } catch (err) {
            console.error('Camera Error:', err);
            alert('Cannot access camera');
        }
    };

    useEffect(() => {
        startCamera(facingMode);
        return () => {
            stream?.getTracks().forEach(t => t.stop());
        };
    }, [facingMode]);

    const capturePhoto = () => {
        if (!videoRef.current || !canvasRef.current) return;
        const video = videoRef.current;
        const canvas = canvasRef.current;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        if (ctx) {
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            canvas.toBlob((blob) => {
                if (blob) {
                    onCapture(blob);
                    onClose();
                }
            }, 'image/jpeg', 0.8);
        }
    };

    return (
        <div className="fixed inset-0 z-[100] bg-black flex flex-col items-center justify-center">
            <video
                ref={videoRef}
                autoPlay
                playsInline
                className="w-full h-full object-cover"
            />
            <canvas ref={canvasRef} className="hidden" />

            {/* Controls */}
            <div className="absolute bottom-10 left-0 right-0 flex items-center justify-around px-10">
                <button
                    onClick={onClose}
                    className="p-4 bg-white/10 backdrop-blur-md rounded-full text-white"
                >
                    <X className="w-6 h-6" />
                </button>

                <button
                    onClick={capturePhoto}
                    className="p-6 bg-white rounded-full shadow-lg active:scale-95 transition-transform"
                >
                    <div className="w-12 h-12 bg-white border-4 border-neutral-900 rounded-full flex items-center justify-center">
                        <Camera className="w-6 h-6 text-neutral-900" />
                    </div>
                </button>

                <button
                    onClick={() => setFacingMode(prev => prev === 'user' ? 'environment' : 'user')}
                    className="p-4 bg-white/10 backdrop-blur-md rounded-full text-white"
                >
                    <RefreshCcw className="w-6 h-6" />
                </button>
            </div>

            <div className="absolute top-10 text-white text-sm font-bold uppercase tracking-widest opacity-50">
                AI Vision Mode
            </div>
        </div>
    );
}
