import asyncio

from sqlalchemy import select

from app.db.init_db import initialize_database
from app.db.models import Email
from app.db.session import AsyncSessionLocal


async def seed_demo_emails() -> None:
    """Insert reusable sample verification emails into MySQL for local testing."""

    await initialize_database()
    async with AsyncSessionLocal() as session:
        test_emails = [
            Email(
                sender="verification.vendor@example.com",
                subject="TEST PASS - Background verification request for Aarav Sharma",
                body="""Hello HR Team,

Please verify the employment details below.

Employee ID: EMP-1001
Employee Name: Aarav Sharma
Date of Joining: 2021-04-12
Last Working Day: 2025-06-30

Regards,
Verification Team""",
            ),
            Email(
                sender="checks@example.com",
                subject="TEST FAIL - One day mismatch for Maya Iyer",
                body="""Dear HR,

Kindly confirm these submitted details.

Employee ID: EMP-1002
Employee Name: Maya Iyer
Date of Joining: 20/01/2020
Last Working Day: 16/12/2024

Thanks""",
            ),
            Email(
                sender="screening.partner@example.com",
                subject="TEST FLAG - Unknown employee verification",
                body="""Hello,

Please verify this candidate's employment information.

Employee ID: EMP-9999
Employee Name: Rohan Mehta
Date of Joining: 2022-03-01
Last Working Day: 2025-01-31

Regards,
Screening Partner""",
            ),
        ]

        for email in test_emails:
            existing = await session.scalar(select(Email.id).where(Email.subject == email.subject))
            if not existing:
                session.add(email)

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed_demo_emails())
    print("Demo MySQL inbox seeded.")
