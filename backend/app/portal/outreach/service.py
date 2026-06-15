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
    OutreachReply,
    PortalLane,
)
from app.portal.outreach import sender, template
from app.portal.outreach.schemas import (
    CarrierReplyRequest,
    CarrierThreadResponse,
    EndCampaignRequest,
    FollowUpRequest,
    OutreachBatchResponse,
    OutreachRequest,
    PreviewResponse,
    RecipientItem,
    ThreadMessage,
)

logger = structlog.get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Source helpers
# ---------------------------------------------------------------------------

def _normalize_source_type(source: str) -> str:
    """Collapse all CRR/FreightX label variants into 'crr_model'."""
    s = source.lower()
    if s == "internal":
        return "internal"
    if s == "dat":
        return "dat"
    if s == "manual":
        return "manual"
    return "crr_model"


def _source_included(source_type: str, req: OutreachRequest) -> bool:
    if source_type == "internal":
        return req.include_internal
    if source_type == "dat":
        return req.include_dat
    if source_type == "crr_model":
        return req.include_crr_model
    return True


_SOURCE_DISPLAY = {
    "internal": "Internal",
    "dat": "DAT",
    "crr_model": "CRR Model",
    "manual": "Manual Emails",
}


# ---------------------------------------------------------------------------
# Recipient resolution
# ---------------------------------------------------------------------------

class _Recipient:
    def __init__(
        self,
        carrier_name: str,
        email: str,
        row_id: uuid.UUID | None = None,
        source_type: str = "internal",
    ):
        self.carrier_name = carrier_name
        self.email = email
        self.row_id = row_id
        self.source_type = source_type


def _resolve_recipients(
    db: Session,
    lane_id: uuid.UUID,
    req: OutreachRequest,
) -> tuple[list[_Recipient], list[str]]:
    """Build final recipient list based on source selection.

    In test_mode: only manual_emails are used (carrier sources skipped).
    In production: carrier sources + any manual_emails combined.
    """
    recipients: list[_Recipient] = []
    sources_seen: list[str] = []

    if req.test_mode:
        for entry in req.manual_emails:
            email = entry.email.strip()
            if email:
                recipients.append(_Recipient(
                    carrier_name=entry.carrier_name or email.split("@")[0],
                    email=email,
                    source_type="manual",
                ))
        return recipients, (["manual"] if recipients else [])

    # --- Production: if NO carrier sources selected, skip DB lookup entirely ---
    no_carrier_sources = (
        not req.include_internal and not req.include_dat and not req.include_crr_model
    )
    if no_carrier_sources:
        for entry in req.manual_emails:
            email = entry.email.strip()
            if email:
                recipients.append(_Recipient(
                    carrier_name=entry.carrier_name or email.split("@")[0],
                    email=email,
                    source_type="manual",
                ))
        return recipients, (["manual"] if recipients else [])

    # --- Production: carrier sources ---
    latest_set = (
        db.query(CarrierOutreachSet)
        .filter_by(lane_id=lane_id, status="ready")
        .order_by(CarrierOutreachSet.created_at.desc())
        .first()
    )
    if latest_set is None:
        # Try to auto-build from whatever is available
        _auto_build_outreach_set(db, lane_id, req)
        latest_set = (
            db.query(CarrierOutreachSet)
            .filter_by(lane_id=lane_id, status="ready")
            .order_by(CarrierOutreachSet.created_at.desc())
            .first()
        )
        if latest_set is None:
            raise ValueError("no_outreach_set")

    rows = (
        db.query(CarrierOutreachRow)
        .filter(CarrierOutreachRow.outreach_set_id == latest_set.id)
        .all()
    )

    for r in rows:
        st = _normalize_source_type(r.source)
        if not _source_included(st, req):
            continue
        if not r.email or not r.email.strip():
            continue
        recipients.append(_Recipient(carrier_name=r.carrier_name, email=r.email, row_id=r.id, source_type=st))
        if st not in sources_seen:
            sources_seen.append(st)

    # --- Manual emails always appended in production mode ---
    for entry in req.manual_emails:
        email = entry.email.strip()
        if email:
            recipients.append(_Recipient(
                carrier_name=entry.carrier_name or email.split("@")[0],
                email=email,
                source_type="manual",
            ))
    if req.manual_emails and "manual" not in sources_seen:
        sources_seen.append("manual")

    return recipients, sources_seen


def _auto_build_outreach_set(db: Session, lane_id: uuid.UUID, req: OutreachRequest) -> None:
    from app.portal.carriers.aggregation import service as agg_service
    try:
        agg_service.build_outreach_set(
            db=db,
            lane_id=lane_id,
            include_internal=req.include_internal,
            include_dat=req.include_dat,
            include_freightx=req.include_crr_model,
            request_id="auto",
        )
    except Exception as exc:
        logger.warning("outreach.auto_build_failed", lane_id=str(lane_id), error=str(exc))


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

def preview(
    db: Session, lane_id: uuid.UUID, req: OutreachRequest, request_id: str = ""
) -> PreviewResponse:
    lane = db.query(PortalLane).filter_by(id=lane_id).first()
    if lane is None:
        raise ValueError("lane_not_found")

    recipients, sources_seen = _resolve_recipients(db, lane_id, req)
    notes = req.notes or (lane.notes or "")
    draft = template.generate(lane, notes)

    logger.info(
        "outreach.preview",
        request_id=request_id,
        lane_id=str(lane_id),
        recipient_count=len(recipients),
        test_mode=req.test_mode,
        sources=sources_seen,
    )

    display_sources = [_SOURCE_DISPLAY.get(s, s) for s in sources_seen]

    by_source: dict[str, int] = {}
    for r in recipients:
        label = _SOURCE_DISPLAY.get(r.source_type, r.source_type)
        by_source[label] = by_source.get(label, 0) + 1

    return PreviewResponse(
        subject=draft.subject,
        body=draft.body,
        html_body=draft.html_body,
        recipients=[RecipientItem(carrier_name=r.carrier_name, email=r.email) for r in recipients],
        recipient_count=len(recipients),
        recipient_count_by_source=by_source,
        sources_included=display_sources,
        test_mode=req.test_mode,
    )


def send(
    db: Session, lane_id: uuid.UUID, req: OutreachRequest, request_id: str = ""
) -> OutreachBatchResponse:
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

    recipients, sources_seen = _resolve_recipients(db, lane_id, req)
    if not recipients:
        raise ValueError("no_valid_recipients")

    notes = req.notes or (lane.notes or "")
    _base_draft = template.generate(lane, notes)  # plain text + subject (shared)
    outreach_set_id = _latest_set_id(db, lane_id) if not req.test_mode else None

    now = _utcnow()
    batch = OutreachBatch(
        id=uuid.uuid4(),
        lane_id=lane_id,
        outreach_set_id=outreach_set_id,
        test_mode=req.test_mode,
        include_internal=req.include_internal,
        include_dat=req.include_dat,
        include_freightx=req.include_crr_model,
        notes=notes or None,
        subject=_base_draft.subject,
        email_body=_base_draft.body,
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
            "subject": _base_draft.subject,
            "text": _base_draft.body,
            "html": template.generate(lane, notes, carrier_name=r.carrier_name or "").html_body,
        }
        for r in recipients
    ]

    provider_ids = sender.send_batch(send_params)

    # Update lane status to in_progress when first send happens
    if lane.status == "new":
        lane.status = "in_progress"
        lane.updated_at = now

    accepted = 0
    for recipient, msg_id in zip(recipients, provider_ids):
        if not msg_id:
            logger.warning("outreach.send.recipient_failed", email=recipient.email, lane_id=str(lane_id))
            continue
        db.add(OutreachMessage(
            id=uuid.uuid4(),
            batch_id=batch.id,
            lane_id=lane_id,
            outreach_row_id=recipient.row_id,
            carrier_name=recipient.carrier_name,
            email_to=recipient.email,
            provider="resend",
            provider_message_id=msg_id,
            status="sent",
            test_mode=req.test_mode,
            source_type=recipient.source_type,
            attempt_number=1,
            is_follow_up=False,
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
        sources=sources_seen,
    )
    return _batch_response(batch)


def send_follow_up(
    db: Session, lane_id: uuid.UUID, req: FollowUpRequest, request_id: str = ""
) -> OutreachBatchResponse:
    lane = db.query(PortalLane).filter_by(id=lane_id).first()
    if lane is None:
        raise ValueError("lane_not_found")
    if lane.status == "completed":
        raise ValueError("campaign_ended")

    # Latest production batch
    original_batch = (
        db.query(OutreachBatch)
        .filter(OutreachBatch.lane_id == lane_id, OutreachBatch.test_mode.is_(False))
        .order_by(OutreachBatch.created_at.desc())
        .first()
    )
    if original_batch is None:
        raise ValueError("no_batch")

    # Non-replied, non-follow-up messages from all production batches for this lane
    all_msgs = (
        db.query(OutreachMessage)
        .join(OutreachBatch, OutreachMessage.batch_id == OutreachBatch.id)
        .filter(
            OutreachBatch.lane_id == lane_id,
            OutreachBatch.test_mode.is_(False),
        )
        .all()
    )
    # Deduplicate by email — only send follow-up to those who haven't replied
    replied_emails = {m.email_to for m in all_msgs if m.replied_at}
    eligible = [
        m for m in all_msgs
        if m.email_to not in replied_emails and not m.is_follow_up
    ]
    # Deduplicate by email (keep first occurrence)
    seen_emails: set[str] = set()
    unique_eligible: list[OutreachMessage] = []
    for m in eligible:
        if m.email_to not in seen_emails:
            seen_emails.add(m.email_to)
            unique_eligible.append(m)

    if not unique_eligible:
        raise ValueError("no_eligible_recipients")

    notes = req.notes or (lane.notes or "")
    draft = template.generate(lane, notes)
    subject = req.subject_override.strip() if req.subject_override.strip() else f"Re: {draft.subject}"

    from_addr = settings.resend_sender
    send_params = [
        {
            "from": from_addr,
            "to": [m.email_to],
            "subject": subject,
            "text": draft.body,
            "html": template.generate(lane, notes, carrier_name=m.carrier_name or "").html_body,
        }
        for m in unique_eligible
    ]

    provider_ids = sender.send_batch(send_params)

    now = _utcnow()
    follow_batch = OutreachBatch(
        id=uuid.uuid4(),
        lane_id=lane_id,
        outreach_set_id=original_batch.outreach_set_id,
        test_mode=False,
        include_internal=original_batch.include_internal,
        include_dat=original_batch.include_dat,
        include_freightx=original_batch.include_freightx,
        notes=notes or None,
        subject=subject,
        email_body=draft.body,
        status="sending",
        sent_count=0,
        created_at=now,
    )
    db.add(follow_batch)
    db.flush()

    accepted = 0
    for original_msg, msg_id in zip(unique_eligible, provider_ids):
        if not msg_id:
            continue
        db.add(OutreachMessage(
            id=uuid.uuid4(),
            batch_id=follow_batch.id,
            lane_id=lane_id,
            outreach_row_id=original_msg.outreach_row_id,
            carrier_name=original_msg.carrier_name,
            email_to=original_msg.email_to,
            provider="resend",
            provider_message_id=msg_id,
            status="sent",
            test_mode=False,
            source_type=original_msg.source_type,
            attempt_number=2,
            is_follow_up=True,
            sent_at=now,
        ))
        accepted += 1

    follow_batch.sent_count = accepted
    follow_batch.status = "sent"
    follow_batch.sent_at = _utcnow()
    db.commit()

    logger.info(
        "outreach.follow_up.complete",
        request_id=request_id,
        lane_id=str(lane_id),
        batch_id=str(follow_batch.id),
        sent_count=accepted,
    )
    return _batch_response(follow_batch)


def end_campaign(
    db: Session, lane_id: uuid.UUID, req: EndCampaignRequest, request_id: str = ""
) -> dict:
    lane = db.query(PortalLane).filter_by(id=lane_id).first()
    if lane is None:
        raise ValueError("lane_not_found")
    lane.status = "completed"
    lane.updated_at = _utcnow()
    db.commit()
    logger.info("outreach.campaign_ended", lane_id=str(lane_id), reason=req.reason, request_id=request_id)
    return {"lane_id": str(lane_id), "status": "completed", "reason": req.reason}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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


def get_carrier_thread(db: Session, lane_id: uuid.UUID, email: str) -> CarrierThreadResponse:
    rows = (
        db.query(OutreachMessage, OutreachBatch)
        .join(OutreachBatch, OutreachMessage.batch_id == OutreachBatch.id)
        .filter(
            OutreachMessage.lane_id == lane_id,
            OutreachMessage.email_to == email,
            OutreachBatch.test_mode.is_(False),
        )
        .order_by(OutreachMessage.sent_at)
        .all()
    )

    replies = (
        db.query(OutreachReply)
        .filter(OutreachReply.lane_id == lane_id, OutreachReply.from_email == email)
        .order_by(OutreachReply.received_at)
        .all()
    )

    carrier_name = rows[0][0].carrier_name if rows else email.split("@")[0]

    items: list[tuple] = []
    for msg, batch in rows:
        items.append((
            msg.sent_at,
            ThreadMessage(
                direction="outbound",
                subject=batch.subject or None,
                body=batch.email_body or None,
                timestamp=_fmt(msg.sent_at) or "",
                status=msg.status,
                attempt_number=msg.attempt_number,
            ),
        ))

    for reply in replies:
        items.append((
            reply.received_at,
            ThreadMessage(
                direction="inbound",
                subject=reply.reply_subject or None,
                body=reply.reply_body or None,
                timestamp=_fmt(reply.received_at) or "",
                from_name=reply.from_name or None,
            ),
        ))

    items.sort(key=lambda x: x[0])
    return CarrierThreadResponse(
        carrier_name=carrier_name,
        email=email,
        messages=[item[1] for item in items],
    )


def send_carrier_reply(
    db: Session, lane_id: uuid.UUID, req: CarrierReplyRequest, request_id: str = ""
) -> dict:
    lane = db.query(PortalLane).filter_by(id=lane_id).first()
    if lane is None:
        raise ValueError("lane_not_found")

    latest_msg = (
        db.query(OutreachMessage)
        .filter(OutreachMessage.lane_id == lane_id, OutreachMessage.email_to == req.email)
        .order_by(OutreachMessage.attempt_number.desc())
        .first()
    )
    next_attempt = (latest_msg.attempt_number + 1) if latest_msg else 1

    html_body = "<br>".join(line for line in req.body.replace("\r\n", "\n").split("\n"))

    provider_ids = sender.send_batch([{
        "from": settings.resend_sender,
        "to": [req.email],
        "subject": req.subject,
        "text": req.body,
        "html": f"<p style='font-family:sans-serif;font-size:14px;line-height:1.6'>{html_body}</p>",
    }])

    msg_id = provider_ids[0] if provider_ids else None
    if not msg_id:
        raise ValueError("send_failed")

    now = _utcnow()
    reply_batch = OutreachBatch(
        id=uuid.uuid4(),
        lane_id=lane_id,
        outreach_set_id=None,
        test_mode=False,
        include_internal=False,
        include_dat=False,
        include_freightx=False,
        notes=None,
        subject=req.subject,
        email_body=req.body,
        status="sent",
        sent_count=1,
        sent_at=now,
        created_at=now,
    )
    db.add(reply_batch)
    db.flush()

    db.add(OutreachMessage(
        id=uuid.uuid4(),
        batch_id=reply_batch.id,
        lane_id=lane_id,
        outreach_row_id=None,
        carrier_name=req.carrier_name or req.email.split("@")[0],
        email_to=req.email,
        provider="resend",
        provider_message_id=msg_id,
        status="sent",
        test_mode=False,
        source_type=latest_msg.source_type if latest_msg else "manual",
        attempt_number=next_attempt,
        is_follow_up=True,
        sent_at=now,
    ))
    db.commit()

    logger.info(
        "outreach.carrier_reply.sent",
        request_id=request_id,
        lane_id=str(lane_id),
        email=req.email,
        attempt=next_attempt,
    )
    return {"status": "sent", "attempt_number": next_attempt}
