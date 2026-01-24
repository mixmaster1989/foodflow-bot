"""
FoodFlow Bot - Health Monitoring Module
Инструменты для мониторинга нагрузки и здоровья бота
"""
import asyncio
import psutil
import time
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class RequestStats:
    """Статистика запросов"""
    total_requests: int = 0
    ai_calls: int = 0
    db_queries: int = 0
    errors: int = 0
    start_time: float = field(default_factory=time.time)
    ai_avg_response_ms: float = 0.0
    last_request_time: Optional[float] = None
    
    def record_request(self):
        self.total_requests += 1
        self.last_request_time = time.time()
    
    def record_ai_call(self, duration_ms: float):
        self.ai_calls += 1
        # Rolling average
        self.ai_avg_response_ms = (
            (self.ai_avg_response_ms * (self.ai_calls - 1) + duration_ms) 
            / self.ai_calls
        )
    
    def record_error(self):
        self.errors += 1
    
    def get_uptime_seconds(self) -> float:
        return time.time() - self.start_time
    
    def get_requests_per_minute(self) -> float:
        uptime = self.get_uptime_seconds()
        if uptime < 60:
            return self.total_requests
        return self.total_requests / (uptime / 60)


# Глобальный объект статистики
stats = RequestStats()


async def get_system_health() -> Dict[str, Any]:
    """Получить полную информацию о здоровье системы"""
    
    # Системные метрики
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Активные процессы Python
    python_procs = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_percent', 'cpu_percent']):
        try:
            if 'python' in proc.info['name'].lower():
                python_procs.append({
                    'pid': proc.info['pid'],
                    'memory_mb': proc.memory_info().rss / (1024 * 1024),
                    'cpu_percent': proc.info['cpu_percent']
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    return {
        'timestamp': datetime.now().isoformat(),
        'uptime_seconds': stats.get_uptime_seconds(),
        
        # Системные ресурсы
        'system': {
            'cpu_percent': cpu_percent,
            'memory_total_gb': memory.total / (1024**3),
            'memory_used_gb': memory.used / (1024**3),
            'memory_available_gb': memory.available / (1024**3),
            'memory_percent': memory.percent,
            'disk_total_gb': disk.total / (1024**3),
            'disk_used_gb': disk.used / (1024**3),
            'disk_free_gb': disk.free / (1024**3),
            'disk_percent': disk.percent,
        },
        
        # Статистика бота
        'bot': {
            'total_requests': stats.total_requests,
            'ai_calls': stats.ai_calls,
            'ai_avg_response_ms': round(stats.ai_avg_response_ms, 2),
            'db_queries': stats.db_queries,
            'errors': stats.errors,
            'requests_per_minute': round(stats.get_requests_per_minute(), 2),
        },
        
        # Python процессы
        'python_processes': python_procs,
        
        # Статус здоровья
        'health_status': _calculate_health_status(cpu_percent, memory.percent, disk.percent)
    }


def _calculate_health_status(cpu: float, mem: float, disk: float) -> str:
    """Определить общий статус здоровья"""
    if cpu > 90 or mem > 90 or disk > 95:
        return '🔴 CRITICAL'
    elif cpu > 70 or mem > 80 or disk > 85:
        return '🟡 WARNING'
    else:
        return '🟢 HEALTHY'


async def get_health_summary() -> str:
    """Получить краткую сводку для логов/алертов"""
    health = await get_system_health()
    
    return (
        f"[Health] {health['health_status']} | "
        f"CPU: {health['system']['cpu_percent']:.1f}% | "
        f"RAM: {health['system']['memory_percent']:.1f}% | "
        f"Disk: {health['system']['disk_percent']:.1f}% | "
        f"Requests: {health['bot']['total_requests']} | "
        f"AI calls: {health['bot']['ai_calls']} (avg {health['bot']['ai_avg_response_ms']}ms) | "
        f"Errors: {health['bot']['errors']}"
    )


# Semaphore для ограничения AI вызовов (Phase 1)
AI_SEMAPHORE: Optional[asyncio.Semaphore] = None
AI_SEMAPHORE_WAITING: int = 0  # Counter for waiting requests

import logging
_sem_logger = logging.getLogger("ai.semaphore")

class LoggingSemaphore:
    """Semaphore wrapper with logging for debugging."""
    
    def __init__(self, value: int):
        self._semaphore = asyncio.Semaphore(value)
        self._max = value
        self._active = 0
        self._waiting = 0
    
    async def __aenter__(self):
        self._waiting += 1
        if self._active >= self._max:
            _sem_logger.info(f"[Semaphore] ⏳ QUEUE: {self._waiting} waiting, {self._active}/{self._max} active")
        await self._semaphore.acquire()
        self._waiting -= 1
        self._active += 1
        _sem_logger.info(f"[Semaphore] ▶️ ACQUIRED: {self._active}/{self._max} active, {self._waiting} waiting")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._active -= 1
        self._semaphore.release()
        _sem_logger.info(f"[Semaphore] ✅ RELEASED: {self._active}/{self._max} active, {self._waiting} waiting")
        return False


_LOGGING_SEMAPHORE: Optional[LoggingSemaphore] = None

def get_ai_semaphore(max_concurrent: int = 5) -> LoggingSemaphore:
    """Получить семафор для ограничения параллельных AI вызовов"""
    global _LOGGING_SEMAPHORE
    if _LOGGING_SEMAPHORE is None:
        _LOGGING_SEMAPHORE = LoggingSemaphore(max_concurrent)
        _sem_logger.info(f"[Semaphore] 🚀 INITIALIZED: max {max_concurrent} concurrent AI calls")
    return _LOGGING_SEMAPHORE
