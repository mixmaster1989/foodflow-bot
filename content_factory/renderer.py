import logging
import os

from PIL import Image, ImageDraw, ImageFont, ImageOps

logger = logging.getLogger(__name__)

class TelegramRenderer:
    """
    Renders Telegram chat bubbles onto a phone mockup.
    """

    def __init__(self, base_image_path: str):
        self.base_image_path = base_image_path
        # Screen coordinates - FINAL TWEAK (-5 left)
        self.screen_region = (374, 208, 657, 812) # [left, top, right, bottom]

        # Paths for icons
        self.emoji_path = "assets/emojis/"

        # Colors (Telegram Dark Theme style)
        self.bg_color = (14, 22, 33)
        self.user_bubble_color = (43, 82, 120)
        self.bot_bubble_color = (24, 37, 51)
        self.text_color = (255, 255, 255)
        self.secondary_text_color = (126, 149, 169)

        try:
            self.font_main = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
            self.font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
            self.font_time = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except Exception:
            self.font_main = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
            self.font_time = ImageFont.load_default()

    def _draw_icon(self, canvas, name, x, y, size=24):
        path = os.path.join(self.emoji_path, f"{name}.png")
        if os.path.exists(path):
            icon = Image.open(path).convert("RGBA")
            icon = icon.resize((size, size), Image.Resampling.LANCZOS)
            canvas.paste(icon, (x, y), icon)
            return size
        return 0

    def render_demo(self, food_photo_path: str, food_name: str, calories: int, protein: float, fat: float, carbs: float, output_path: str):
        """
        Creates a composite image: Phone -> Chat -> (User Photo + Bot Reply)
        """
        if not os.path.exists(self.base_image_path):
            self.base_image_path = "/home/user1/foodflow-bot_new/" + self.base_image_path

        phone = Image.open(self.base_image_path).convert("RGBA")

        # 2. Create the "Screen Content"
        screen_w = self.screen_region[2] - self.screen_region[0]
        screen_h = self.screen_region[3] - self.screen_region[1]
        screen = Image.new("RGBA", (screen_w, screen_h), self.bg_color)
        draw = ImageDraw.Draw(screen)

        # --- Draw User Message (Photo) ---
        user_msg_y = 80
        bubble_w = 230
        bubble_h = 170

        if os.path.exists(food_photo_path):
            food_img = Image.open(food_photo_path).convert("RGB")
            food_img = ImageOps.fit(food_img, (bubble_w, bubble_h))

            mask = Image.new("L", (bubble_w, bubble_h), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([0, 0, bubble_w, bubble_h], radius=20, fill=255)

            screen.paste(food_img, (screen_w - bubble_w - 15, user_msg_y), mask)

        # --- Draw Bot Message (Analysis) ---
        bot_msg_y = user_msg_y + bubble_h + 15
        bot_bubble_w = 250
        bot_bubble_h = 220

        draw.rounded_rectangle(
            [15, bot_msg_y, 15 + bot_bubble_w, bot_msg_y + bot_bubble_h],
            radius=20, fill=self.bot_bubble_color
        )

        margin = 20
        self._draw_icon(screen, "check", 15 + margin, bot_msg_y + margin - 2, 26)
        draw.text((15 + margin + 35, bot_msg_y + margin), "Готово!", font=self.font_main, fill=(74, 187, 126))

        self._draw_icon(screen, "plate", 15 + margin, bot_msg_y + margin + 40, 22)
        draw.text((15 + margin + 30, bot_msg_y + margin + 40), f"{food_name}", font=self.font_small, fill=self.text_color)

        stats_y = bot_msg_y + margin + 80
        self._draw_icon(screen, "fire", 15 + margin, stats_y, 20)
        draw.text((15 + margin + 30, stats_y), f"Калории: {calories} ккал", font=self.font_small, fill=self.text_color)

        self._draw_icon(screen, "meat", 15 + margin, stats_y + 30, 20)
        draw.text((15 + margin + 30, stats_y + 30), f"Белки: {protein}г", font=self.font_small, fill=self.text_color)

        self._draw_icon(screen, "avocado", 15 + margin, stats_y + 60, 20)
        draw.text((15 + margin + 30, stats_y + 60), f"Жиры: {fat}г", font=self.font_small, fill=self.text_color)

        self._draw_icon(screen, "bread", 15 + margin, stats_y + 90, 20)
        draw.text((15 + margin + 30, stats_y + 90), f"Углеводы: {carbs}г", font=self.font_small, fill=self.text_color)

        draw.text((15 + bot_bubble_w - 55, bot_msg_y + bot_bubble_h - 25), "12:05", font=self.font_time, fill=self.secondary_text_color)

        # 3. Apply Rounded Corners to the WHOLE SCREEN before pasting
        screen_mask = Image.new("L", (screen_w, screen_h), 0)
        screen_mask_draw = ImageDraw.Draw(screen_mask)
        # Phone screen usually has ~30-40px radius
        screen_mask_draw.rounded_rectangle([0, 0, screen_w, screen_h], radius=35, fill=255)

        # 4. Compositing
        phone.paste(screen, (self.screen_region[0], self.screen_region[1]), screen_mask)

        phone.save(output_path, "PNG")
        logger.info(f"✨ Mockup rendered and saved to: {output_path}")
        return output_path

        # 4. Save
        phone.save(output_path, "PNG")
        logger.info(f"✨ Mockup rendered and saved to: {output_path}")
        return output_path

if __name__ == "__main__":
    # Test run
    logging.basicConfig(level=logging.INFO)
    renderer = TelegramRenderer("content_factory/image_refs/mockup_phone_base.png")
    renderer.render_demo(
        food_photo_path="assets/demo_breakfast.png",
        food_name="Завтрак чемпиона",
        calories=450,
        protein=20.5,
        fat=15.0,
        carbs=35.0,
        output_path="content_factory/runs/test_mockup.png"
    )
