import os
import logging
from io import BytesIO
from datetime import date
from jinja2 import Template
import cairosvg
from pathlib import Path

logger = logging.getLogger("services.svg_renderer")

# Path setup
TEMPLATE_PATH = Path(__file__).parent / "templates" / "dashboard.svg"

def draw_svg_dashboard(
    user_name: str,
    target_date: date,
    logs: list,
    total_metrics: dict,
    goals: dict,
    water_total: int = 0
) -> BytesIO:
    """
    Renders a premium nutrition dashboard using SVG + Jinja2 + CairoSVG.
    """
    try:
        # Sanitize and ensure all keys exist in total_metrics
        if not isinstance(total_metrics, dict):
            total_metrics = {}
        else:
            total_metrics = dict(total_metrics)

        defaults_totals = {
            "calories": 0.0,
            "protein": 0.0,
            "fat": 0.0,
            "carbs": 0.0,
            "fiber": 0.0
        }
        for k, v in defaults_totals.items():
            if k not in total_metrics or total_metrics[k] is None:
                total_metrics[k] = v
            else:
                try:
                    total_metrics[k] = float(total_metrics[k])
                except (ValueError, TypeError):
                    total_metrics[k] = v

        # Sanitize and ensure all keys exist in goals
        if not isinstance(goals, dict):
            goals = {}
        else:
            goals = dict(goals)

        defaults_goals = {
            "calories": 2000,
            "protein": 100,
            "fat": 70,
            "carbs": 250,
            "fiber": 30,
            "water": 2000
        }
        for k, v in defaults_goals.items():
            if k not in goals or goals[k] is None or goals[k] == 0:
                goals[k] = v
            else:
                try:
                    goals[k] = float(goals[k])
                    if goals[k] == 0:
                        goals[k] = v
                except (ValueError, TypeError):
                    goals[k] = v

        # 1. Prepare Template
        with open(TEMPLATE_PATH, "r") as f:
            template = Template(f.read())

        # 2. Geometry calculations
        # Calories Ring: radius=100 -> circumference approx 628
        circumference = 2 * 3.14159 * 100
        cals = total_metrics.get("calories", 0)
        goal = goals.get("calories", 2000)
        
        pct = min(1.0, cals / goal) if goal > 0 else 0
        offset = circumference * (1 - pct)

        # Dynamic height for WOW layout
        # Base (750) + logs (len * 90) + footer (100)
        calculated_height = max(900, 750 + len(logs) * 90 + 100)

        # 3. Context for Jinja2
        from utils.i18n import t
        context = {
            "height": calculated_height,
            "user_name": user_name,
            "date": target_date.strftime("%d.%m.%Y"),
            "totals": total_metrics,
            "goals": goals,
            "logs": logs,
            "water_total": water_total,
            "cal_circumference": circumference,
            "cal_offset": offset,
            "min": min, # Helper for template
            "int": int,
            "round": round,
            "t": t
        }

        # 4. Render SVG string
        svg_content = template.render(**context)

        # 5. Convert to PNG
        png_output = BytesIO()
        cairosvg.svg2png(
            bytestring=svg_content.encode("utf-8"),
            write_to=png_output,
            output_width=800 # Match SVG width
        )
        png_output.seek(0)
        
        logger.info(f"✅ SVG Dashboard rendered for {user_name} ({len(logs)} logs)")
        return png_output

    except Exception as e:
        logger.error(f"❌ SVG Rendering failed: {e}", exc_info=True)
        # Return None so the caller can fallback to Pillow or text
        return None

# Alias for backward compatibility
draw_daily_card = draw_svg_dashboard

if __name__ == "__main__":
    # Test script
    from datetime import datetime
    
    class MockLog:
        def __init__(self, t, n, c):
            self.date = t
            self.product_name = n
            self.calories = c

    now = datetime.now()
    test_logs = [
        MockLog(now, "Омлет с лососем и авокадо", 450),
        MockLog(now, "Кофе на миндальном молоке", 85),
        MockLog(now, "Протеиновый батончик", 210),
        MockLog(now, "Салат Цезарь с креветками", 320)
    ]
    
    metrics = {"calories": 1065, "protein": 65, "fat": 42, "carbs": 55, "fiber": 8}
    user_goals = {"calories": 2000, "protein": 120, "fat": 70, "carbs": 200, "water": 2500}
    
    bio = draw_svg_dashboard("Igor", now.date(), test_logs, metrics, user_goals, water_total=1200)
    if bio:
        with open("premium_dashboard.png", "wb") as f:
            f.write(bio.getbuffer())
        print("🚀 Premium dashboard generated: premium_dashboard.png")
