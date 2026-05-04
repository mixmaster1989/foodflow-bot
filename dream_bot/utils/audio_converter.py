import asyncio
import os
import logging

async def convert_ogg_to_wav(input_path: str, output_path: str):
    """Конвертирует Telegram OGG (Opus) в WAV (PCM16, 24kHz) для OpenAI"""
    process = await asyncio.create_subprocess_exec(
        'ffmpeg', '-y', '-i', input_path,
        '-ar', '24000', '-ac', '1', '-c:a', 'pcm_s16le',
        output_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        logging.error(f"FFmpeg conversion error: {stderr.decode()}")
        return False
    return True

async def convert_mp3_to_ogg(input_path: str, output_path: str) -> bool:
    """Конвертирует MP3 (TTS-ответ) в OGG/Opus для Telegram."""
    process = await asyncio.create_subprocess_exec(
        'ffmpeg', '-y', '-i', input_path,
        '-c:a', 'libopus', '-b:a', '32k',
        output_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        logging.error(f"FFmpeg mp3→ogg error: {stderr.decode()}")
        return False
    return True


async def convert_wav_to_ogg(input_path: str, output_path: str):
    """
    Конвертирует WAV или сырой PCM16 (s16le, 24k) обратно в OGG/Opus для Telegram.
    Мы добавляем параметры для случая, если файл - это сырой pcm16 без заголовка.
    """
    # Если файл не имеет заголовка (pcm16), мы подсказываем ffmpeg параметры входа
    command = [
        'ffmpeg', '-y',
        '-f', 's16le', '-ar', '24000', '-ac', '1', '-i', input_path,
        '-c:a', 'libopus', '-b:a', '32k',
        output_path
    ]
    
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    
    # Если не вышло как pcm (например, там нормальный wav), пробуем обычный режим
    if process.returncode != 0:
        process = await asyncio.create_subprocess_exec(
            'ffmpeg', '-y', '-i', input_path,
            '-c:a', 'libopus', '-b:a', '32k',
            output_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

    if process.returncode != 0:
        logging.error(f"FFmpeg conversion error: {stderr.decode()}")
        return False
    return True
