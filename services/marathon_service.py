from sqlalchemy.future import select
from sqlalchemy.orm import Session
from database.models import User, Marathon, MarathonParticipant
from datetime import datetime

class MarathonService:
    @staticmethod
    async def get_marathon_by_id(session: Session, marathon_id: int) -> Marathon | None:
        stmt = select(Marathon).where(Marathon.id == marathon_id)
        return (await session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def is_user_participating(session: Session, user_id: int) -> bool:
        """Check if user is in ANY active marathon."""
        stmt = select(MarathonParticipant).join(Marathon).where(
            MarathonParticipant.user_id == user_id,
            MarathonParticipant.is_active == True,
            Marathon.is_active == True,
            Marathon.end_date > datetime.utcnow()
        )
        participant = (await session.execute(stmt)).first()
        return participant is not None

    @staticmethod
    async def process_invite(session: Session, marathon_invite: str | int, user_id: int, user_info: dict) -> dict:
        """
        Process invite link m_{id} or m_{token}.
        
        Returns:
            dict: {
                "success": bool, 
                "message": str, 
                "is_new_user": bool,
                "marathon_name": str
            }
        """
        # 1. Validate Marathon
        marathon = None
        try:
            m_id = int(marathon_invite)
            marathon = await MarathonService.get_marathon_by_id(session, m_id)
        except ValueError:
            # It's a string token
            stmt = select(Marathon).where(Marathon.invite_token == str(marathon_invite))
            marathon = (await session.execute(stmt)).scalar_one_or_none()
            
            if marathon and marathon.invite_token_expires_at:
                if marathon.invite_token_expires_at < datetime.utcnow():
                    return {"success": False, "message": "Эта ссылка-приглашение истекла."}

        if not marathon:
            return {"success": False, "message": "Марафон не найден."}
            
        if not marathon.is_active:
             return {"success": False, "message": "Этот марафон завершен."}

        marathon_id = marathon.id

        # Check Registration Toggle
        if not getattr(marathon, "is_registration_open", True): # Safe getattr pending persistence
             return {"success": False, "message": "Регистрация на этот марафон закрыта."}

        # 2. Get or Create User
        stmt = select(User).where(User.id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        is_new_user = False
        
        if not user:
            # Create new user logic
            is_new_user = True
            user = User(
                id=user_id,
                username=user_info.get("username"),
                first_name=user_info.get("first_name"),
                last_name=user_info.get("last_name"),
                is_verified=True, # Auto-verify via link
                curator_id=None   # IMPORTANT: Not a ward!
            )
            session.add(user)
            await session.flush() # Get ID if needed, though we set it manually
        
        # 3. Check Conflicts
        # Check if already in THIS marathon
        stmt_part = select(MarathonParticipant).where(
            MarathonParticipant.user_id == user_id,
            MarathonParticipant.marathon_id == marathon_id
        )
        existing_part = (await session.execute(stmt_part)).scalar_one_or_none()
        
        if existing_part:
            if existing_part.is_active:
                return {"success": False, "message": "Вы уже участник этого марафона!"}
            else:
                # Was kicked or left? Reactivate?
                existing_part.is_active = True
                await session.commit() # Ensure update is saved
                return {"success": True, "message": "Вы вернулись в марафон!", "is_new_user": is_new_user, "marathon_name": marathon.name}

        # Check if in OTHER active marathon
        if await MarathonService.is_user_participating(session, user_id):
             return {"success": False, "message": "Вы уже участвуете в другом активном марафоне. Нельзя быть в двух сразу."}
             
        # 4. Add to Marathon
        new_part = MarathonParticipant(
            marathon_id=marathon_id,
            user_id=user_id,
            is_active=True,
            start_weight=None # Will be filled during onboarding/later
        )
        session.add(new_part)
        await session.commit() # SAVE IT!
        
        return {
            "success": True, 
            "message": f"Вы успешно присоединились к марафону '{marathon.name}'!",
            "is_new_user": is_new_user,
            "marathon_name": marathon.name,
            "curator_id": marathon.curator_id
        }
