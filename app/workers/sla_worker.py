import asyncio
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update, func, or_
from app.core.database import AsyncSessionLocal
from app.models.office_lead import OfficeLead, LeadStatus
from app.models.office_bdm import OfficeBdmReview
from app.models.office_audit import OfficeAuditLog

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("office_sla_worker")

async def evaluate_bdm_sla_breaches():
    """Scans and flags leads that have exceeded the 24-hour BDM review SLA."""
    async with AsyncSessionLocal() as session:
        cutoff_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)

        # Find leads in PENDING_BDM_REVIEW older than 24h
        stmt = (
            select(OfficeLead)
            .where(
                OfficeLead.status == LeadStatus.PENDING_BDM_REVIEW,
                OfficeLead.updated_at < cutoff_time
            )
        )
        leads = (await session.execute(stmt)).scalars().all()

        if not leads:
            logger.info("[SLA_WORKER] No active BDM review SLA breaches detected.")
            return

        logger.warning(f"[SLA_WORKER] Detected {len(leads)} BDM SLA breach(es). Processing...")

        for lead in leads:
            # Audit the breach into the system log
            audit_entry = OfficeAuditLog(
                actor_id=None,
                actor_email="SYSTEM_WORKER",
                actor_role="WORKER",
                method="CRON",
                route_path="sla_worker/bdm_breach",
                status_code=200,
                latency_ms=0,
                action_description=f"Automated 24h BDM SLA Breach Flagged for Lead {lead.lead_code}",
                metadata_payload={
                    "lead_id": str(lead.id),
                    "lead_code": lead.lead_code,
                    "assigned_bdm_id": str(lead.assigned_bdm_id) if lead.assigned_bdm_id else None,
                    "escalated_at": lead.updated_at.isoformat()
                }
            )
            session.add(audit_entry)

        await session.commit()
        logger.info(f"[SLA_WORKER] Successfully logged audit breaches for {len(leads)} lead(s).")

async def run_periodic_checks(interval_seconds: int = 300):
    """Runs the background checks continuously every 5 minutes."""
    logger.info(f"[SLA_WORKER] Background SLA Engine started. Polling every {interval_seconds}s...")
    while True:
        try:
            await evaluate_bdm_sla_breaches()
        except Exception as e:
            logger.error(f"[SLA_WORKER] Error during SLA evaluation cycle: {e}", exc_info=True)
        await asyncio.sleep(interval_seconds)

if __name__ == "__main__":
    asyncio.run(run_periodic_checks())