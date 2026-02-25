"""Universal Input Router — Multimodal Processing."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from api.auth import CurrentUser, DBSession
from services.voice_stt import SpeechToText
from services.ai_brain import AIBrainService
from services.normalization import NormalizationService
import os
import shutil
import logging

from services.herbalife_expert import herbalife_expert
from database.base import get_db

router = APIRouter()
logger = logging.getLogger("api.universal")
stt_engine = SpeechToText()

async def resolve_input_intent(text: str):
    """Deep intent resolution logic ported from universal_input.py."""
    
    # 1. Herbalife Shortcut (Highest Priority)
    hl_product = await herbalife_expert.find_product_by_alias(text)
    if hl_product:
        qty_data = herbalife_expert.parse_quantity(text)
        nutr = herbalife_expert.calculate_nutrition(hl_product, qty_data["amount"], qty_data["unit"])
        return {
            "type": "herbalife",
            "product": hl_product,
            "nutrition": nutr,
            "text": text
        }
    
    # 2. AI Brain Analysis
    brain_result = await AIBrainService.analyze_text(text)
    normalization = await NormalizationService.analyze_food_intake(text)
    
    intent = brain_result.get("intent", "unknown") if brain_result else "unknown"
    
    return {
        "type": "standard",
        "intent": intent,
        "brain": brain_result,
        "normalization": normalization,
        "text": text
    }

@router.post("/process")
async def process_universal(
    text: str = Form(None),
    file: UploadFile = File(None),
    user: CurrentUser = None
):
    """Unified entry point for multimodal input processing."""
    print(f"\n[DEBUG] --- Universal Process Request Start ---", flush=True)
    print(f"[DEBUG] Text param: '{text}'", flush=True)
    print(f"[DEBUG] File param: {file.filename if file else 'None'}", flush=True)
    
    final_text = text
    
    # 1. Handle File (Voice or Image)
    if file:
        ct = file.content_type or ""
        fname = file.filename or ""
        print(f"[DEBUG] Handling File: {fname} (type: {ct})", flush=True)
        
        is_audio = ct.startswith("audio/") or ct == "video/webm" or "voice" in fname.lower() or "webm" in fname.lower()
        is_image = ct.startswith("image/") or "image" in fname.lower() or "jpg" in fname.lower() or "png" in fname.lower()
        
        print(f"[DEBUG] Detection: is_audio={is_audio}, is_image={is_image}", flush=True)
        
        if is_audio:
            temp_path = f"services/temp/api_voice_{fname}"
            os.makedirs("services/temp", exist_ok=True)
            try:
                content = await file.read()
                print(f"[DEBUG] Audio bytes read: {len(content)}", flush=True)
                if len(content) < 100:
                    print(f"[DEBUG] Audio too small, skipping", flush=True)
                    return {"success": False, "message": "Voice recording too short or empty"}
                    
                with open(temp_path, "wb") as buffer:
                    buffer.write(content)
                
                final_text = await stt_engine.process_voice_message(temp_path)
                print(f"[DEBUG] STT Result: '{final_text}'", flush=True)
                if not final_text:
                    print(f"[DEBUG] STT Failed to transcribe", flush=True)
                    return {"success": False, "message": "Could not recognize speech. Try again."}
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        
        elif is_image:
            from services.ai import AIService
            image_bytes = await file.read()
            print(f"[DEBUG] Image bytes read: {len(image_bytes)}", flush=True)
            recognition = await AIService.recognize_product_from_image(image_bytes)
            final_text = recognition.get("name") if recognition else final_text
            print(f"[DEBUG] Image Recognition Result: '{final_text}'", flush=True)
        else:
            print(f"[DEBUG] Unknown file type provided", flush=True)
    
    # 2. Resolve Intent and Data
    if not final_text:
        print(f"[DEBUG] Process FAILED: final_text is empty or multimodal recognition failed", flush=True)
        return {"success": False, "message": "Не удалось распознать продукт. Попробуйте сфоткать еду или четко продиктовать название."}
        
    print(f"[DEBUG] Proceeding to resolve intent for: '{final_text}'", flush=True)
    try:
        result = await resolve_input_intent(final_text)
        print(f"[DEBUG] Result Type: {result.get('type')}", flush=True)
        
        # Check if it's actually food
        if result.get("type") == "standard":
            intent = result.get("intent", "unknown")
            norm = result.get("normalization")
            
            # If AI couldn't normalize it or intent is not food-related
            if intent == "unknown" and (not norm or not norm.get("name")):
                 return {
                    "success": False, 
                    "message": f"Я вижу что-то похожее на '{final_text}', но это не похоже на еду. Я — фуд-бот, давай лучше про еду! 🍎"
                }
                
    except Exception as e:
        print(f"[DEBUG] ERROR in resolve_input_intent: {e}", flush=True)
        raise HTTPException(status_code=500, detail=f"Internal logic error: {str(e)}")
    
    print(f"[DEBUG] --- Process SUCCESS ---\n", flush=True)
    return {
        "success": True,
        "text": final_text,
        "analysis": result
    }
