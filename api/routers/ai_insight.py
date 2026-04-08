from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from api.auth import CurrentUser
from api.dependencies import get_db_session
from sqlalchemy.ext.asyncio import AsyncSession
from services.ai_insight import AIInsightService
from services.ai_guide import AIGuideService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Smart Analytics"])

@router.get("/insight")
async def get_ai_insight(
    user: CurrentUser,
    action: str = "greeting",
    detail: str = "Just opened the app",
    db: AsyncSession = Depends(get_db_session)
):
    """
    Returns an SSE stream of AI commentary.
    Phantom mode: subtle, semi-transparent, non-blocking.
    """
    print(f"DEBUG: GET /api/ai/insight called by {user.id}")
    
    # CRITICAL: Fetch context OUTSIDE the generator because the DB session 
    # will be closed after this function returns the StreamingResponse object.
    context = await AIInsightService.get_user_context(user.id, db)
    print(f"DEBUG: context fetched: {context}")

    is_heavy_action = action in ["food_log", "water_logged"]
    guide_active = await AIGuideService.is_active(user.id, db)

    async def event_generator():
        print(f"DEBUG: event_generator started. Action: {action}")
        
        # Route to Большой Гид if action is heavy and Guide is paid/active
        if is_heavy_action and guide_active:
            try:
                if action == "water_logged":
                    try:
                        amount_ml = int(''.join(filter(str.isdigit, detail))) if detail else 200
                    except:
                        amount_ml = 200
                    gen = await AIGuideService.get_water_advice(user.id, amount_ml, db, stream=True)
                else:
                    current_meal = {
                        "name": detail, 
                        "calories": "см. в дневнике", 
                        "time": "сейчас",
                        "protein": "?",
                        "fat": "?",
                        "carbs": "?"
                    }
                    gen = await AIGuideService.get_contextual_advice(user.id, current_meal, db, stream=True)
                
                if gen:
                    async for token in gen:
                        yield f"data: {token}\n\n"
                    # Exit generator to prevent triggering Whisperer
                    return
            except Exception as e:
                logger.error(f"Error streaming from AIGuideService: {e}")
                # If it failed, gracefully fallback to Whisperer below
        
        # Fallback / Lightweight Action Route: Phantom Whisperer
        async for token in AIInsightService.generate_insight_stream(
            user_id=user.id,
            context=context,
            action_type=action,
            action_detail=detail
        ):
            # SSE format: data: <content>\n\n
            yield f"data: {token}\n\n"

    print(f"DEBUG: returning StreamingResponse")
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
