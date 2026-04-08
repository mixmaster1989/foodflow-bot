import json
from datetime import datetime

def analyze_stats(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    results = []
    
    for user in data:
        u_id = user['user_id']
        name = f"{user['profile']['first_name']} {user['profile']['last_name'] or ''}".strip()
        
        cons_logs = user.get('consumption_logs', [])
        water_logs = user.get('water_logs', [])
        weight_logs = user.get('weight_logs', [])
        
        # Сбор всех дат
        all_dates = []
        for l in cons_logs: all_dates.append(datetime.fromisoformat(l['date']))
        for l in water_logs: all_dates.append(datetime.fromisoformat(l['date']))
        for l in weight_logs: all_dates.append(datetime.fromisoformat(l['date']))
        
        if not all_dates:
            results.append({
                "name": name,
                "id": u_id,
                "period": 0,
                "cons_count": 0,
                "water_count": 0,
                "weight_count": 0,
                "status": "❌ Нет данных"
            })
            continue
            
        first_date = min(all_dates)
        last_date = max(all_dates)
        period_days = (last_date - first_date).days + 1
        
        # Оценка качества
        # Хорошо: > 7 дней активности и > 20 логов еды
        status = "🔴 Мало данных"
        if period_days >= 7 and len(cons_logs) >= 20:
            status = "🟢 Отлично"
        elif period_days >= 3 or len(cons_logs) >= 10:
            status = "🟡 Средне"
            
        results.append({
            "name": name,
            "id": u_id,
            "period": period_days,
            "cons_count": len(cons_logs),
            "water_count": len(water_logs),
            "weight_count": len(weight_logs),
            "status": status
        })
        
    # Сортировка по количеству логов еды
    results.sort(key=lambda x: x['cons_count'], reverse=True)
    
    print(f"{'Имя':<25} | {'Дней':<5} | {'Еда':<5} | {'Вода':<5} | {'Вес':<5} | {'Статус'}")
    print("-" * 70)
    for r in results:
        print(f"{r['name'][:25]:<25} | {r['period']:<5} | {r['cons_count']:<5} | {r['water_count']:<5} | {r['weight_count']:<5} | {r['status']}")

if __name__ == "__main__":
    analyze_stats('data/march_8_stats.json')
