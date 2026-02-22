
import os
from datetime import datetime, date
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

# Constants
WIDTH = 800
HEIGHT = 1200 # Adjustable based on content
BG_COLOR = (20, 20, 24) # Dark grey/almost black #141418
CARD_BG_COLOR = (44, 44, 46) # Lighter grey for cards
TEXT_COLOR = (255, 255, 255)
ACCENT_COLOR = (255, 165, 0) # Orange
SECONDARY_TEXT_COLOR = (160, 160, 160)

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def load_font(size, bold=False):
    path = FONT_PATH if bold else FONT_REGULAR_PATH
    try:
        return ImageFont.truetype(path, size)
    except IOError:
        return ImageFont.load_default()

def draw_daily_card(
    user_name: str,
    target_date: date,
    logs: list, # List of ConsumptionLog
    total_metrics: dict, # {calories, protein, fat, carbs}
    goals: dict, # {calories}
    water_total: int = 0
) -> BytesIO:
    """Generate a visual daily summary card."""
    
    # Create base image
    # Calculate dynamic height? For now fixed enough for ~10 items
    img_height = max(1000, 400 + len(logs) * 80)
    image = Image.new('RGB', (WIDTH, img_height), color=BG_COLOR)
    draw = ImageDraw.Draw(image)
    
    # 1. Header
    title_font = load_font(48, True)
    subtitle_font = load_font(24)
    
    draw.text((40, 40), user_name, font=title_font, fill=TEXT_COLOR)
    draw.text((40, 100), f"Отчет за {target_date.strftime('%d.%m.%Y')}", font=subtitle_font, fill=SECONDARY_TEXT_COLOR)
    
    # 2. Macros Summary Card
    card_y = 160
    card_h = 340 # Increased for Fiber
    draw.rectangle([20, card_y, WIDTH-20, card_y+card_h], fill=CARD_BG_COLOR, outline=None, width=0)
    
    # Calories Circle
    # Draw arc for calories
    center_x = 150
    center_y = card_y + card_h // 2
    radius = 80
    bbox = [center_x-radius, center_y-radius, center_x+radius, center_y+radius]
    
    # Background ring
    draw.arc(bbox, start=0, end=360, fill=(60, 60, 60), width=15)
    
    # Progress ring
    cals = int(total_metrics.get("calories", 0))
    goal = int(goals.get("calories", 2000))
    if goal > 0:
        pct = min(1.0, cals / goal)
        angle = 360 * pct
        # Pillow arcs start from 3 o'clock clockwise? No, 3 o'clock is 0. 
        # -90 is 12 o'clock.
        draw.arc(bbox, start=-90, end=-90+angle, fill=ACCENT_COLOR, width=15)
    
    # Text inside ring
    cal_font = load_font(36, True)
    text_bbox = draw.textbbox((0, 0), str(cals), font=cal_font)
    tw = text_bbox[2] - text_bbox[0]
    th = text_bbox[3] - text_bbox[1]
    draw.text((center_x - tw/2, center_y - th/2 - 5), str(cals), font=cal_font, fill=TEXT_COLOR)
    
    label_font = load_font(16)
    draw.text((center_x - 20, center_y + 20), "ккал", font=label_font, fill=SECONDARY_TEXT_COLOR)
    
    # Macros Lines
    macro_start_x = 300
    macro_y = card_y + 60
    
    def draw_macro_line(label, value, color, y_pos):
        # Label
        draw.text((macro_start_x, y_pos), label, font=load_font(24), fill=SECONDARY_TEXT_COLOR)
        # Value
        draw.text((macro_start_x + 100, y_pos), f"{value:.1f}г", font=load_font(24, True), fill=TEXT_COLOR)
        # Bar background
        bar_x = macro_start_x + 200
        bar_w = 250
        draw.rectangle([bar_x, y_pos+5, bar_x+bar_w, y_pos+20], fill=(60,60,60))
        # Bar fill (dummy scale, assuming max 200g roughly?)
        bar_fill = min(1.0, value / 150) # Arbitrary scale for visual
        draw.rectangle([bar_x, y_pos+5, bar_x + int(bar_w*bar_fill), y_pos+20], fill=color)

    p = total_metrics.get("protein", 0)
    f = total_metrics.get("fat", 0)
    carbs = total_metrics.get("carbs", 0) # Renamed c to carbs for clarity with the edit
    fiber = total_metrics.get("fiber", 0) # Renamed fib to fiber for clarity with the edit
    
    draw_macro_line("Белки", p, (255, 99, 71), macro_y)
    draw_macro_line("Жиры", f, (255, 215, 0), macro_y + 60)
    draw_macro_line("Углеводы", carbs, (100, 149, 237), macro_y + 120) # Used existing color
    if fiber > 0: # Kept the conditional check
        draw_macro_line("Клетчатка", fiber, (50, 205, 50), macro_y + 180) # Lime Green

    # 3. Water Progress Bar
    water_y = macro_y + 250
    # Label and Icon
    draw.text((30, water_y), "💦 Вода", font=load_font(24), fill=TEXT_COLOR)
    # Value vs Goal
    water_goal = goals.get("water", 2000)
    draw.text((macro_start_x + 100, water_y), f"{water_total}/{water_goal} мл", font=load_font(24, True), fill=TEXT_COLOR)
    
    # Water bar 
    bar_x = 30
    bar_y = water_y + 40
    bar_w = WIDTH - 60
    bar_h = 15
    draw.rounded_rectangle([bar_x, bar_y, bar_x+bar_w, bar_y+bar_h], radius=7, fill=(60, 60, 60))
    if water_goal > 0:
        water_pct = min(1.0, water_total / water_goal)
        if water_pct > 0:
            draw.rounded_rectangle([bar_x, bar_y, bar_x+(bar_w*water_pct), bar_y+bar_h], radius=7, fill=(64, 164, 255)) # Blue color

    
    # 4. Item List
    list_y = card_y + card_h + 30 # Adjusted list_y to account for water bar
    # ... rest of list drawing ...
    draw.text((40, list_y), "Приемы пищи:", font=load_font(32, True), fill=TEXT_COLOR)
    list_y += 60
    
    item_font = load_font(24)
    time_font = load_font(20)
    cal_small_font = load_font(24, True)
    
    for log in logs:
        # Time
        time_str = log.date.strftime("%H:%M")
        draw.text((40, list_y), time_str, font=time_font, fill=SECONDARY_TEXT_COLOR)
        
        # Product Line
        # Truncate text
        product_text = log.product_name
        if len(product_text) > 40:
            product_text = product_text[:37] + "..."
            
        draw.text((120, list_y-5), product_text, font=item_font, fill=TEXT_COLOR)
        
        # Calories
        draw.text((WIDTH-120, list_y-5), f"{int(log.calories)}", font=cal_small_font, fill=TEXT_COLOR)
        
        list_y += 50
        
        # Line separator
        draw.line([40, list_y, WIDTH-40, list_y], fill=(60,60,60), width=1)
        list_y += 20
        
    # Output
    bio = BytesIO()
    image.save(bio, format='PNG')
    bio.seek(0)
    return bio

if __name__ == "__main__":
    # Test
    # Mock logs
    class MockLog:
        def __init__(self, t, n, c):
            self.date = t
            self.product_name = n
            self.calories = c
            
    now = datetime.now()
    logs = [
        MockLog(now, "Яблоко", 52),
        MockLog(now, "Куриная грудка с рисом и овощами терияки", 450),
        MockLog(now, "Кофе с молоком", 120),
    ]
    bio = draw_daily_card("Test User", now.date(), logs, {"calories": 622, "protein": 40, "fat": 20, "carbs": 80}, {"calories": 2000})
    with open("test_card.png", "wb") as f:
        f.write(bio.getbuffer())
    print("Test card generated: test_card.png")
