from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.auth import AuthContext
from app.config import get_settings
from app.linkedin_api import _publish_existing_job
from app.linkedin_store import claim_due_publish_jobs


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("linkedin-worker")


async def process_once(limit: int) -> int:
    settings = get_settings()
    jobs = await asyncio.to_thread(claim_due_publish_jobs, settings, limit=limit)
    if not jobs:
        return 0
    completed = 0
    for job in jobs:
        auth = AuthContext(user_id=job.user_id, business_id=job.business_id)
        try:
            await _publish_existing_job(settings, auth, job)
            completed += 1
            logger.info("Published LinkedIn scheduled job id=%s", job.id)
        except Exception as exc:
            logger.warning("LinkedIn scheduled job failed id=%s error=%s", job.id, str(exc))
    return completed


async def main() -> None:
    parser = argparse.ArgumentParser(description="Process due GrowMino LinkedIn scheduled posts.")
    parser.add_argument("--once", action="store_true", help="Process due jobs once and exit.")
    parser.add_argument("--interval", type=int, default=60, help="Polling interval in seconds.")
    parser.add_argument("--limit", type=int, default=5, help="Max jobs to claim per tick.")
    args = parser.parse_args()

    if args.once:
        count = await process_once(args.limit)
        logger.info("Processed %s LinkedIn job(s).", count)
        return

    logger.info("LinkedIn worker started interval=%ss limit=%s", args.interval, args.limit)
    while True:
        await process_once(args.limit)
        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    asyncio.run(main())
