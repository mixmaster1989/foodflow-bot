
import asyncio
from services.reports import generate_admin_stats_csv

async def test_csv():
    csv_io = await generate_admin_stats_csv(days=5)
    content = csv_io.getvalue().decode('utf-8')
    print("-" * 30)
    print(content)
    print("-" * 30)

if __name__ == "__main__":
    asyncio.run(test_csv())
