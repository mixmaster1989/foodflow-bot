"""
Voice Transcription Module (STT) - Copied from IKAR 2.0
Uses SpeechRecognition + FFMPEG + Google Free API
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger("voice.stt")

class SpeechToText:
    """
    Класс для преобразования речи в текст.
    """

    def __init__(self):
        """
        Инициализирует STT движок.
        """
        self.use_speech_recognition = True

        try:
            import speech_recognition as sr
            self.recognizer = sr.Recognizer()
            logger.info("SpeechRecognition инициализирован")
        except ImportError:
            logger.error("SpeechRecognition не установлен. Установите: pip install SpeechRecognition")
            self.use_speech_recognition = False

    def _convert_to_wav(self, input_path: str) -> str | None:
        """
        Конвертирует аудио в WAV через ffmpeg. Это намного быстрее чем librosa.
        """
        try:
            # Создаем папку temp если не существует
            temp_dir = Path(__file__).parent / "temp"
            temp_dir.mkdir(exist_ok=True)

            # Путь для WAV файла
            input_filename = os.path.basename(input_path)
            wav_filename = f"{os.path.splitext(input_filename)[0]}.wav"
            wav_path = temp_dir / wav_filename

            logger.info(f"🔄 КОНВЕРТИРУЕМ В WAV ЧЕРЕЗ FFMPEG: {input_path}")
            print(f"🔄 FFMPEG: {os.path.basename(input_path)} -> WAV")

            # Используем ffmpeg для быстрой конвертации (force overwrite, 16kHz, mono)
            import subprocess
            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-ar", "16000",
                "-ac", "1",
                str(wav_path)
            ]

            result = subprocess.run(cmd, capture_output=True)

            if result.returncode != 0:
                logger.error(f"Ffmpeg error: {result.stderr.decode()}")
                return None

            logger.info(f"✅ КОНВЕРТАЦИЯ ЗАВЕРШЕНА: {wav_path}")
            print(f"✅ СОЗДАН WAV: {wav_path.name}")

            return str(wav_path)

        except Exception as e:
            logger.error(f"Ошибка конвертации: {e}")
            print(f"❌ ОШИБКА КОНВЕРТАЦИИ: {e}")
            return None

    def speech_to_text(self, audio_path: str) -> str:
        """
        Преобразует речь в текст.
        """
        if not self.use_speech_recognition:
            return "STT не доступен"

        wav_path = None

        try:
            import speech_recognition as sr

            # Проверяем существование файла
            if not os.path.exists(audio_path):
                logger.error(f"Аудиофайл не найден: {audio_path}")
                return ""

            # Проверяем размер файла
            file_size = os.path.getsize(audio_path)
            logger.info(f"Обрабатываем аудиофайл: {audio_path} (размер: {file_size} байт)")

            if file_size == 0:
                logger.error("Аудиофайл пустой")
                return ""

            # Конвертируем в WAV если нужно
            if not audio_path.lower().endswith('.wav'):
                wav_path = self._convert_to_wav(audio_path)
                if not wav_path:
                    return ""
                process_path = wav_path
            else:
                process_path = audio_path

            logger.info(f"🎤 ЗАПУСКАЕМ SPEECH RECOGNITION: {process_path}")
            print(f"🎤 РАСПОЗНАЕМ РЕЧЬ: {os.path.basename(process_path)}")

            # Загружаем аудиофайл
            with sr.AudioFile(process_path) as source:
                # Записываем аудио
                audio = self.recognizer.record(source)

                # Распознаем речь через Google API (бесплатно)
                text = self.recognizer.recognize_google(audio, language='ru-RU')

                logger.info(f"✅ РАСПОЗНАННЫЙ ТЕКСТ: {text}")
                print(f"🗣️ РАСПОЗНАНО: {text}")
                return text

        except Exception as e:
            logger.error(f"❌ ОШИБКА ПРИ РАСПОЗНАВАНИИ РЕЧИ: {e}")
            print(f"❌ ОШИБКА STT: {e}")
            return ""
        finally:
            # Удаляем временный WAV файл
            if wav_path and os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                    logger.info(f"🗑️ УДАЛЕН ВРЕМЕННЫЙ WAV: {wav_path}")
                except Exception:
                    pass

    async def process_voice_message(self, file_path: str) -> str:
        """
        Обрабатывает голосовое сообщение.
        """
        try:
            logger.info(f"🎤 НАЧИНАЕМ ОБРАБОТКУ ГОЛОСОВОГО ФАЙЛА: {file_path}")
            print(f"🎤 ОБРАБАТЫВАЕМ ГОЛОС: {os.path.basename(file_path)}")

            # Проверяем файл
            if not os.path.exists(file_path):
                logger.error(f"❌ ФАЙЛ НЕ СУЩЕСТВУЕТ: {file_path}")
                print(f"❌ ФАЙЛ НЕ НАЙДЕН: {file_path}")
                return ""

            # Распознаем речь
            text = self.speech_to_text(file_path)
            return text

        except Exception as e:
            logger.error(f"❌ ОШИБКА ПРИ ОБРАБОТКЕ ГОЛОСОВОГО СООБЩЕНИЯ: {e}")
            print(f"❌ ОШИБКА ОБРАБОТКИ ГОЛОСА: {e}")
            return ""
