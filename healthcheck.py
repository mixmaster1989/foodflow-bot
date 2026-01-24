#!/usr/bin/env python3
"""
FoodFlow Health Check CLI
Быстрая проверка состояния бота и системы
"""
import asyncio
import json
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from monitoring import get_system_health, get_health_summary

async def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--json':
        health = await get_system_health()
        print(json.dumps(health, indent=2, default=str))
    else:
        # Красивый вывод
        health = await get_system_health()
        summary = await get_health_summary()
        
        print("=" * 60)
        print("🍲 FOODFLOW BOT HEALTH CHECK")
        print("=" * 60)
        print(f"\n⏰ Timestamp: {health['timestamp']}")
        print(f"📊 Status: {health['health_status']}")
        print(f"⏱️  Uptime: {health['uptime_seconds']:.0f}s")
        
        print("\n--- SYSTEM RESOURCES ---")
        sys_info = health['system']
        print(f"💻 CPU:    {sys_info['cpu_percent']:.1f}%")
        print(f"🧠 RAM:    {sys_info['memory_used_gb']:.1f}GB / {sys_info['memory_total_gb']:.1f}GB ({sys_info['memory_percent']:.1f}%)")
        print(f"💾 Disk:   {sys_info['disk_used_gb']:.1f}GB / {sys_info['disk_total_gb']:.1f}GB ({sys_info['disk_percent']:.1f}%)")
        
        print("\n--- BOT STATS ---")
        bot_info = health['bot']
        print(f"📨 Total requests:    {bot_info['total_requests']}")
        print(f"🤖 AI calls:          {bot_info['ai_calls']}")
        print(f"⚡ AI avg response:   {bot_info['ai_avg_response_ms']}ms")
        print(f"💾 DB queries:        {bot_info['db_queries']}")
        print(f"❌ Errors:            {bot_info['errors']}")
        print(f"📈 Req/min:           {bot_info['requests_per_minute']}")
        
        if health['python_processes']:
            print("\n--- PYTHON PROCESSES ---")
            for proc in health['python_processes']:
                print(f"  PID {proc['pid']}: {proc['memory_mb']:.1f}MB RAM, {proc['cpu_percent']:.1f}% CPU")
        
        print("\n" + "=" * 60)

if __name__ == '__main__':
    asyncio.run(main())
