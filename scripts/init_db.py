import asyncio
from pathlib import Path
import sys

# Add project root directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import bcrypt
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
import app.models  # Ensures all models are registered on Base.metadata


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


async def build_tables_and_seed():
    print("\n--- Synchronizing Database Schema ---")
    host_target = settings.ASYNC_DATABASE_URL.split("@")[-1]
    print(f"[INFO] Connecting to target database: {host_target}")

    async with engine.begin() as conn:
        await conn.run_sync(app.models.Base.metadata.create_all)
    print("[OK] PostgreSQL tables created successfully.")

    async with AsyncSessionLocal() as session:
        # Determine whether the enum uses SUPER_ADMIN or SUPERADMIN
        role_val = getattr(
            app.models.OfficeRole,
            "SUPER_ADMIN",
            getattr(app.models.OfficeRole, "SUPERADMIN", None),
        )

        # 1. Check Super Admin existence
        stmt = select(app.models.OfficeUser).where(
            app.models.OfficeUser.email == settings.SUPERADMIN_EMAIL
        )
        result = await session.execute(stmt)
        admin = result.scalar_one_or_none()

        if not admin:
            admin_user = app.models.OfficeUser(
                email=settings.SUPERADMIN_EMAIL,
                password_hash=hash_password(settings.SUPERADMIN_PASSWORD),
                first_name="Master",
                last_name="Admin",
                role=role_val,
                state_code="HQ",
                is_active=True,
            )
            session.add(admin_user)
            await session.flush()

            # 2. Check and Seed Linked Employee Node
            emp_stmt = select(app.models.OfficeEmployee).where(
                app.models.OfficeEmployee.emp_code == "EMP-BAC-001"
            )
            emp_result = await session.execute(emp_stmt)
            existing_emp = emp_result.scalar_one_or_none()

            if not existing_emp:
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
            print(
                f"[INFO] Superadmin already exists: {settings.SUPERADMIN_EMAIL}"
            )


if __name__ == "__main__":
    asyncio.run(build_tables_and_seed())