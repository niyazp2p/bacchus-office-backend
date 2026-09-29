import sys
from pathlib import Path

# Add project root directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import asyncio
from sqlalchemy import select
from app.core.config import settings
from app.core.database import engine, AsyncSessionLocal
import app.models  # Ensures all models are registered on Base.metadata
from app.core.security import hash_password

async def build_tables_and_seed():
    print("\n--- Synchronizing Database Schema ---")
    async with engine.begin() as conn:
        await conn.run_sync(app.models.Base.metadata.create_all)
    print("[OK] PostgreSQL tables created successfully.")

    async with AsyncSessionLocal() as session:
        # Check Super Admin existence
        stmt = select(app.models.OfficeUser).where(app.models.OfficeUser.email == settings.SUPERADMIN_EMAIL)
        result = await session.execute(stmt)
        admin = result.scalar_one_or_none()

        if not admin:
            admin_user = app.models.OfficeUser(
                email=settings.SUPERADMIN_EMAIL,
                password_hash=hash_password(settings.SUPERADMIN_PASSWORD),
                first_name="Master",
                last_name="Admin",
                role=app.models.OfficeRole.SUPER_ADMIN,
                state_code="HQ",
                is_active=True,
            )
            session.add(admin_user)
            await session.flush()

            # Seed Linked Employee Node
            admin_employee = app.models.OfficeEmployee(
                user_id=admin_user.id,
                emp_code="EMP-BAC-001",
                department="EXECUTIVE",
                designation="CMD / Master Administrator",
                reporting_to_id=None,
                is_field_staff=False,
            )
            session.add(admin_employee)
            await session.commit()
            print(f"[OK] Master Superadmin seeded: {settings.SUPERADMIN_EMAIL}")
        else:
            print(f"[INFO] Superadmin already exists: {settings.SUPERADMIN_EMAIL}")

if __name__ == "__main__":
    asyncio.run(build_tables_and_seed())