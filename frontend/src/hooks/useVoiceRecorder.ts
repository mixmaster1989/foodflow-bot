import { useState, useRef } from 'react';

export function useVoiceRecorder() {
    const [isRecording, setIsRecording] = useState(false);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const audioChunksRef = useRef<Blob[]>([]);

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream);
            mediaRecorderRef.current = mediaRecorder;
            audioChunksRef.current = [];

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunksRef.current.push(event.data);
                }
            };

            mediaRecorder.start(200); // Send data chunks every 200ms
            setIsRecording(true);
        } catch (err) {
            console.error('Error accessing microphone:', err);
            alert('Cannot access microphone. Please check permissions.');
        }
    };

    const stopRecording = (): Promise<Blob> => {
        return new Promise((resolve) => {
            if (!mediaRecorderRef.current) return;

            mediaRecorderRef.current.onstop = () => {
                const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
                mediaRecorderRef.current?.stream.getTracks().forEach(track => track.stop());
                setIsRecording(false);
                resolve(audioBlob);
            };

            mediaRecorderRef.current.stop();
        });
    };

    return { isRecording, startRecording, stopRecording };
}
