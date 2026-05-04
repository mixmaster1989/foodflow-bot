import { useState, useRef } from 'react';

export function useVoiceRecorder() {
    const [isRecording, setIsRecording] = useState(false);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const audioChunksRef = useRef<Blob[]>([]);

    const startRecording = async () => {
        console.log('[VoiceRecorder] startRecording called');
        try {
            console.log('[VoiceRecorder] Requesting microphone access...');
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            console.log('[VoiceRecorder] Microphone access granted, creating MediaRecorder...');
            const mediaRecorder = new MediaRecorder(stream);
            mediaRecorderRef.current = mediaRecorder;
            audioChunksRef.current = [];

            mediaRecorder.ondataavailable = (event) => {
                console.log(`[VoiceRecorder] Data available: ${event.data.size} bytes`);
                if (event.data.size > 0) {
                    audioChunksRef.current.push(event.data);
                }
            };

            mediaRecorder.onerror = (event) => {
                console.error('[VoiceRecorder] MediaRecorder error:', event);
                console.error('Ошибка записи (MediaRecorder Error)');
            };

            mediaRecorder.start(200); // Send data chunks every 200ms
            console.log('[VoiceRecorder] MediaRecorder started');
            setIsRecording(true);
        } catch (err) {
            console.error('[VoiceRecorder] Error accessing microphone:', err);
            console.error('Cannot access microphone:', err);
        }
    };

    const stopRecording = (): Promise<Blob> => {
        console.log('[VoiceRecorder] stopRecording called');
        return new Promise((resolve) => {
            if (!mediaRecorderRef.current) {
                console.warn('[VoiceRecorder] No active media recorder found!');
                return;
            }

            mediaRecorderRef.current.onstop = () => {
                console.log('[VoiceRecorder] MediaRecorder stopped. Assembling blob...');
                const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
                console.log(`[VoiceRecorder] Blob assembled, size: ${audioBlob.size} bytes`);
                mediaRecorderRef.current?.stream.getTracks().forEach(track => {
                    console.log(`[VoiceRecorder] Stopping audio track...`);
                    track.stop();
                });
                setIsRecording(false);
                resolve(audioBlob);
            };

            console.log('[VoiceRecorder] Ordering MediaRecorder to stop...');
            mediaRecorderRef.current.stop();
        });
    };

    return { isRecording, startRecording, stopRecording };
}
