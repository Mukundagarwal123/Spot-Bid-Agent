from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db.models import (
    CarrierOutreachRow,
    CarrierOutreachSet,
    OutreachBatch,
    OutreachMessage,
    PortalLane,
)
from app.portal.outreach import sender, template
from app.portal.outreach.schemas import (
    OutreachBatchResponse,
    OutreachRequest,
    PreviewResponse,
    RecipientItem,
)

logger = structlog.get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def preview(db: Session, lane_id: uuid.UUID, req: OutreachRequest, request_id: str = "") -> PreviewResponse:
    lane = db.query(PortalLane).filter_by(id=lane_id).first()
    if lane is None:
        raise ValueError("lane_not_found")

    recipients, sources_included = _resolve_recipients(db, lane_id, req)

    draft = template.generate(lane, req.notes)

    logger.info(
        "outreach.preview",
        request_id=request_id,
        lane_id=str(lane_id),
        recipient_count=len(recipients),
        test_mode=req.test_mode,
        sources=sources_included,
    )

    return PreviewResponse(
        subject=draft.subject,
        body=draft.body,
        recipients=[RecipientItem(carrier_name=r.carrier_name, email=r.email) for r in recipients],
        recipient_count=len(recipients),
        sources_included=sources_included,
        test_mode=req.test_mode,
    )


def send(db: Session, lane_id: uuid.UUID, req: OutreachRequest, request_id: str = "") -> OutreachBatchResponse:
    lane = db.query(PortalLane).filter_by(id=lane_id).first()
    if lane is None:
        raise ValueError("lane_not_found")

    # Idempotency guard: return existing batch if send was initiated recently
    cutoff = _utcnow() - timedelta(minutes=5)
    existing = (
        db.query(OutreachBatch)
        .filter(
            OutreachBatch.lane_id == lane_id,
            OutreachBatch.test_mode == req.test_mode,
            OutreachBatch.status.in_(["sending", "sent"]),
            OutreachBatch.created_at >= cutoff,
        )
        .order_by(OutreachBatch.created_at.desc())
        .first()
    )
    if existing:
        logger.info("outreach.send.idempotent_return", lane_id=str(lane_id), batch_id=str(existing.id))
        return _batch_response(existing)

    recipients, sources_included = _resolve_recipients(db, lane_id, req)
    if not recipients:
        raise ValueError("no_valid_recipients")

    draft = template.generate(lane, req.notes)

    outreach_set_id = _latest_set_id(db, lane_id) if not req.test_mode else None

    now = _utcnow()
    batch = OutreachBatch(
        id=uuid.uuid4(),
        lane_id=lane_id,
        outreach_set_id=outreach_set_id,
        test_mode=req.test_mode,
        include_internal=req.include_internal,
        include_dat=req.include_dat,
        include_freightx=req.include_freightx,
        notes=req.notes or None,
        subject=draft.subject,
        email_body=draft.body,
        status="sending",
        sent_count=0,
        created_at=now,
    )
    db.add(batch)
    db.flush()

    from_addr = settings.resend_sender
    send_params = [
        {
            "from": from_addr,
            "to": [r.email],
            "subject": draft.subject,
            "text": draft.body,
        }
        for r in recipients
    ]

    provider_ids = sender.send_batch(send_params)

    accepted = 0
    for recipient, msg_id in zip(recipients, provider_ids):
        if not msg_id:
            logger.warning("outreach.send.recipient_failed", email=recipient.email, lane_id=str(lane_id))
            continue
        db.add(OutreachMessage(
            id=uuid.uuid4(),
            batch_id=batch.id,
            lane_id=lane_id,
            outreach_row_id=recipient.row_id if hasattr(recipient, "row_id") else None,
            carrier_name=recipient.carrier_name,
            email_to=recipient.email,
            provider="resend",
            provider_message_id=msg_id,
            status="sent",
            test_mode=req.test_mode,
            sent_at=now,
        ))
        accepted += 1

    batch.sent_count = accepted
    batch.status = "sent"
    batch.sent_at = _utcnow()
    db.commit()

    logger.info(
        "outreach.send.complete",
        request_id=request_id,
        lane_id=str(lane_id),
        batch_id=str(batch.id),
        sent_count=accepted,
        test_mode=req.test_mode,
    )
    return _batch_response(batch)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class _Recipient:
    def __init__(self, carrier_name: str, email: str, row_id: uuid.UUID | None = None):
        self.carrier_name = carrier_name
        self.email = email
        self.row_id = row_id


def _resolve_recipients(
    db: Session,
    lane_id: uuid.UUID,
    req: OutreachRequest,
) -> tuple[list[_Recipient], list[str]]:
    if req.test_mode:
        recipients = [_Recipient(carrier_name="(test)", email=e) for e in req.manual_emails]
        return recipients, []

    latest_set = (
        db.query(CarrierOutreachSet)
        .filter_by(lane_id=lane_id, status="ready")
        .order_by(CarrierOutreachSet.created_at.desc())
        .first()
    )
    if latest_set is None:
        raise ValueError("no_outreach_set")

    source_labels: dict[str, bool] = {
        "internal": req.include_internal,
        "dat": req.include_dat,
    }

    rows = (
        db.query(CarrierOutreachRow)
        .filter(CarrierOutreachRow.outreach_set_id == latest_set.id)
        .all()
    )

    def _source_included(source: str) -> bool:
        if source.lower() == "internal":
            return req.include_internal
        if source.lower() == "dat":
            return req.include_dat
        # FreightX rows have labels like "1_2", "1_4", or "freightx"
        return req.include_freightx

    recipients = [
        _Recipient(carrier_name=r.carrier_name, email=r.email, row_id=r.id)
        for r in rows
        if r.email and r.email.strip() and _source_included(r.source)
    ]

    sources_included = [
        s for s, included in [
            ("internal", req.include_internal),
            ("dat", req.include_dat),
            ("freightx", req.include_freightx),
        ] if included
    ]

    # Convert _Recipient → RecipientItem for the response (reuse class below)
    return recipients, sources_included  # type: ignore[return-value]


def _latest_set_id(db: Session, lane_id: uuid.UUID) -> uuid.UUID | None:
    s = (
        db.query(CarrierOutreachSet)
        .filter_by(lane_id=lane_id, status="ready")
        .order_by(CarrierOutreachSet.created_at.desc())
        .first()
    )
    return s.id if s else None


def _batch_response(batch: OutreachBatch) -> OutreachBatchResponse:
    return OutreachBatchResponse(
        batch_id=str(batch.id),
        lane_id=str(batch.lane_id),
        status=batch.status,
        sent_count=batch.sent_count,
        test_mode=batch.test_mode,
    )
