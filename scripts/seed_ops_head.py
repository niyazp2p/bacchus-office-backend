import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.database import AsyncSessionLocal
from app.models.office_auth import OfficeUser, OfficeEmployee, OfficeRole
from app.core.security import hash_password
from sqlalchemy import select

async def seed_ops():
    async with AsyncSessionLocal() as s:
        existing = await s.scalar(select(OfficeUser.id).where(OfficeUser.email == "ops@bacchus.com"))
        if existing:
            print(">>> Operations Head already provisioned <<<")
            return

        ops_user = OfficeUser(
            email="ops@bacchus.com",
            password_hash=hash_password("Pass123!"),
            first_name="OP",
            last_name="Head",
            role=OfficeRole.OPERATIONS_HEAD,
            state_code="DL"
        )
        s.add(ops_user)
        await s.flush()

        ops_emp = OfficeEmployee(
            user_id=ops_user.id,
            emp_code="EMP-OPS-001",
            department="OPERATIONS",
            designation="VP of Distillery Operations & Compliance",
        )
        s.add(ops_emp)
        await s.commit()
        print(">>> OPERATIONS HEAD SEEDED: ops@bacchus.com / Pass123! (EMP-OPS-001) <<<")

if __name__ == "__main__":
    asyncio.run(seed_ops())