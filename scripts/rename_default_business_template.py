"""
Script to rename database global master template from "默认商务模板" to "商务模板".
Run this from project root: python scripts/rename_default_business_template.py
"""
import asyncio
import logging
import sys

sys.path.insert(0, "e:/pyprojects/FlowSlide")

from src.flowslide.database.database import AsyncSessionLocal
from src.flowslide.database.repositories import GlobalMasterTemplateRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLD_NAME = "默认商务模板"
NEW_NAME = "商务模板"

async def main():
    async with AsyncSessionLocal() as session:
        repo = GlobalMasterTemplateRepository(session)
        # find templates with OLD_NAME
        from sqlalchemy import select
        from src.flowslide.database.models import GlobalMasterTemplate

        stmt = select(GlobalMasterTemplate).where(GlobalMasterTemplate.template_name == OLD_NAME)
        result = await session.execute(stmt)
        rows = result.scalars().all()

        if not rows:
            logger.info(f"No templates found with name '{OLD_NAME}'")
            return

        for tpl in rows:
            logger.info(f"Updating template id={tpl.id} name='{tpl.template_name}' -> '{NEW_NAME}'")
            tpl.template_name = NEW_NAME
            await session.flush()

        await session.commit()
        logger.info(f"Updated {len(rows)} template(s)")

if __name__ == '__main__':
    asyncio.run(main())
