from fastapi import APIRouter, Request
import logging

router = APIRouter()
logger = logging.getLogger("api.debug")

@router.post("/log")
async def remote_log(request: Request):
    try:
        data = await request.json()
        msg = data.get("message", "No message")
        level = data.get("level", "INFO")
        detail = data.get("detail", "")
        
        # Log to server console/logs
        log_msg = f"📱 [MOBILE-DEBUG] {msg} | {detail}"
        if level == "ERROR":
            logger.error(log_msg)
        else:
            logger.info(log_msg)
            
        return {"status": "received"}
    except Exception as e:
        logger.error(f"Error in remote logging: {e}")
        return {"status": "error", "message": str(e)}
