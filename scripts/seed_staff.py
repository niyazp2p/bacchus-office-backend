import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.database import AsyncSessionLocal
from app.models.office_auth import OfficeUser, OfficeEmployee, OfficeRole
from app.core.security import hash_password

async def seed():
    async with AsyncSessionLocal() as s:
        # 1. Seed BDM
        bdm = OfficeUser(
            email="bdm@bacchus.com",
            password_hash=hash_password("Pass123!"),
            first_name="Vikram",
            last_name="Malhotra",
            role=OfficeRole.BDM,
            state_code="DL"
        )
        s.add(bdm)
        await s.flush()

        bdm_emp = OfficeEmployee(
            user_id=bdm.id,
            emp_code="EMP-BDM-001",
            department="SALES",
            designation="Business Development Manager"
        )
        s.add(bdm_emp)
        await s.flush()

        # 2. Seed Telecaller 1
        tc1 = OfficeUser(
            email="caller1@bacchus.com",
            password_hash=hash_password("Pass123!"),
            first_name="Priya",
            last_name="Sharma",
            role=OfficeRole.TELECALLER,
            state_code="DL"
        )
        s.add(tc1)
        await s.flush()

        tc1_emp = OfficeEmployee(
            user_id=tc1.id,
            emp_code="EMP-TC-001",
            department="TELECALLING",
            designation="Telecaller Representative",
            reporting_to_id=bdm_emp.id
        )
        s.add(tc1_emp)

        # 3. Seed Telecaller 2
        tc2 = OfficeUser(
            email="caller2@bacchus.com",
            password_hash=hash_password("Pass123!"),
            first_name="Neha",
            last_name="Verma",
            role=OfficeRole.TELECALLER,
            state_code="DL"
        )
        s.add(tc2)
        await s.flush()

        tc2_emp = OfficeEmployee(
            user_id=tc2.id,
            emp_code="EMP-TC-002",
            department="TELECALLING",
            designation="Telecaller Representative",
            reporting_to_id=bdm_emp.id
        )
        s.add(tc2_emp)

        await s.commit()
        print(">>> EMPLOYEES SEEDED SUCCESSFULLY <<<")

if __name__ == "__main__":
    asyncio.run(seed())