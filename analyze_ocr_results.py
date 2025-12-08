import json

with open('ocr_test_results_20251126_152827.json', 'r') as f:
    results = json.load(f)

print('📊 АНАЛИЗ РЕЗУЛЬТАТОВ OCR МОДЕЛЕЙ\n')
print('=' * 100)

# Успешные модели с хорошим качеством
successful = [r for r in results if r['status'] == 'success' and r.get('response_quality') == 'good']

print(f'\n✅ УСПЕШНЫЕ МОДЕЛИ (качество: good): {len(successful)}\n')
print(f"{'Модель':<45} {'Время(мс)':<12} {'Токены':<20} {'Стоимость':<15} {'Товаров':<10}")
print('-' * 100)

for r in sorted(successful, key=lambda x: x.get('cost_usd', 999) or 999):
    model_short = r['model'].split('/')[-1][:42]
    time_str = f"{r['response_time_ms']:.0f}"
    tokens_str = f"{r['input_tokens']}+{r['output_tokens']}={r['total_tokens']}"
    cost_str = f"${r['cost_usd']:.6f}" if r['cost_usd'] else 'FREE'
    items = r.get('items_count', 0)
    print(f"{model_short:<45} {time_str:<12} {tokens_str:<20} {cost_str:<15} {items:<10}")

# Лучшие по критериям
print('\n' + '=' * 100)
print('\n🏆 ЛУЧШИЕ ВЫБОРЫ:\n')

# Самый дешевый (платный)
paid_successful = [r for r in successful if r.get('cost_usd', 0) > 0]
if paid_successful:
    cheapest = min(paid_successful, key=lambda x: x['cost_usd'])
    print(f"💰 САМЫЙ ДЕШЕВЫЙ (платный): {cheapest['model']}")
    print(f"   Стоимость: ${cheapest['cost_usd']:.6f} | Время: {cheapest['response_time_ms']:.0f}мс | Товаров: {cheapest.get('items_count', 0)}")

# Самый быстрый
fastest = min(successful, key=lambda x: x['response_time_ms'] or 999999)
print(f"\n⚡ САМЫЙ БЫСТРЫЙ: {fastest['model']}")
print(f"   Время: {fastest['response_time_ms']:.0f}мс | Стоимость: ${fastest.get('cost_usd', 0):.6f} | Товаров: {fastest.get('items_count', 0)}")

# Бесплатные
free_successful = [r for r in successful if r.get('cost_usd', 0) == 0]
if free_successful:
    print(f"\n🆓 БЕСПЛАТНЫЕ МОДЕЛИ: {len(free_successful)}")
    for r in free_successful:
        print(f"   • {r['model']} | Время: {r['response_time_ms']:.0f}мс | Товаров: {r.get('items_count', 0)}")

# Неудачные
failed = [r for r in results if r['status'] != 'success' or r.get('response_quality') != 'good']
print(f"\n❌ НЕУДАЧНЫЕ/ПРОБЛЕМНЫЕ: {len(failed)}\n")
for r in failed:
    reason = r.get('error', 'invalid_json')[:60]
    print(f"   • {r['model'].split('/')[-1]}: {r['status']} - {reason}")

print('\n' + '=' * 100)
total_cost = sum(r.get('cost_usd', 0) or 0 for r in results)
print(f'\n💰 Общая стоимость тестирования: ${total_cost:.6f}')


