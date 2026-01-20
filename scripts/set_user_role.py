import asyncio
import sys
import os
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.base import async_session
from database.models import User

async def set_user_role(user_id: int, role: str):
    print(f"Attempting to set role '{role}' for user ID: {user_id}")
    async with async_session() as session:
        # Check if user exists
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            print(f"User {user_id} found. Current role: {user.role}. Setting new role: {role}")
            user.role = role
            await session.commit()
            print(f"Role for user {user_id} successfully updated to '{role}'.")
        else:
            print(f"User {user_id} not found in the database. Cannot update role.")
            # Optionally, create user if not found? For now, just report.
            # print(f"Creating new user {user_id} with role '{role}'...")
            # new_user = User(id=user_id, username=f"user_{user_id}", role=role, is_verified=True)
            # session.add(new_user)
            # await session.commit()
            # print(f"New user {user_id} created with role '{role}'.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 set_user_role.py <user_id> <role>")
        sys.exit(1)

    user_id_str = sys.argv[1]
    role_to_set = sys.argv[2]

    try:
        user_id_int = int(user_id_str)
    except ValueError:
        print(f"Invalid user_id: {user_id_str}. Must be an integer.")
        sys.exit(1)
    
    # Basic validation for role
    if role_to_set not in ["user", "curator", "admin"]:
        print(f"Invalid role: {role_to_set}. Role must be 'user', 'curator', or 'admin'.")
        sys.exit(1)

    asyncio.run(set_user_role(user_id_int, role_to_set))
