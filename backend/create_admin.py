import asyncio
import logging
from app.db.session import AsyncSessionLocal
from app.services.auth_service import create_user

# Configure logging to match your application's format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

async def bootstrap_admin():
    async with AsyncSessionLocal() as db:
        logger.info("Creating initial admin user...")
        try:
            admin = await create_user(
                db=db,
                full_name="Super Admin",
                email="admin@company.com",          # Change this to your preferred admin email
                password="SecurePassword123!",      # Change this to your preferred password
                role="admin"                        # This automatically grants full write access
            )
            logger.info(f"Success! Admin user created with email: {admin.email}")
        except ValueError as e:
            logger.warning(f"Notice: {e}. (An admin might already exist).")

if __name__ == "__main__":
    asyncio.run(bootstrap_admin())