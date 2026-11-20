import asyncio

from app.tasks.detect_creative_fatigue import (
    CreativeFatigueTask
)

from app.tasks.generate_daily_reports import (
    DailyReportTask
)

from app.tasks.generate_weekly_reports import (
    WeeklyReportTask
)

from app.tasks.sync_discord_orders import (
    DiscordOrderSyncTask
)

from app.tasks.sync_meta_ads import (
    MetaAdsSyncTask
)


class StartupManager:

    # ===================================
    # START BACKGROUND TASKS
    # ===================================

    @staticmethod
    async def start_background_tasks(business_ids: list[int]):
        if not business_ids or any(
            isinstance(item, bool) or item <= 0 for item in business_ids
        ):
            raise ValueError("Explicit valid business IDs are required for background tasks.")

        # The FastAPI lifespan intentionally does not call this yet. Operators
        # must explicitly supply provisioned businesses after reviewing each job.
        for business_id in sorted(set(business_ids)):
            asyncio.create_task(CreativeFatigueTask.run(business_id))
            asyncio.create_task(DailyReportTask.run(business_id))
            asyncio.create_task(WeeklyReportTask.run(business_id))
            asyncio.create_task(DiscordOrderSyncTask.run(business_id))
            asyncio.create_task(MetaAdsSyncTask.run(business_id))

        print("Tenant-context background tasks started for the selected businesses.")
