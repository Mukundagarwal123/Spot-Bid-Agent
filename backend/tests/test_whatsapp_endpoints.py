"""Integration tests for WhatsApp inbox endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.db import base as db_base
from app.db.models import MessagingContact, MessagingConversation, MessagingMessage
from app.services.whatsapp_service import ingest_inbound_message


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _seed_thread() -> tuple[str, str]:
    contact_id = uuid.uuid4()
    conv_id = uuid.uuid4()
    msg_id = uuid.uuid4()

    with db_base.session_scope() as db:
        contact = MessagingContact(
            id=contact_id,
            phone="18057332428",
            display_name="Kansal",
            wa_id="18057332428",
            labels_json='["priority"]',
            created_at=_now(),
            updated_at=_now(),
        )
        conv = MessagingConversation(
            id=conv_id,
            contact_id=contact_id,
            channel="whatsapp",
            status="open",
            unread_count=2,
            last_message_preview="Hey whats up",
            last_activity_at=_now(),
            last_inbound_at=_now(),
            created_at=_now(),
            updated_at=_now(),
        )
        msg = MessagingMessage(
            id=msg_id,
            conversation_id=conv_id,
            contact_id=contact_id,
            direction="inbound",
            body="Hey whats up",
            provider="meta_whatsapp",
            provider_message_id="wamid.test.1",
            status="received",
            received_at=_now(),
            created_at=_now(),
        )
        db.add_all([contact, conv, msg])
        db.commit()

    return str(conv_id), str(contact_id)


def test_messages_endpoint_marks_thread_read(client) -> None:
    conv_id, _ = _seed_thread()

    response = client.get(f"/api/whatsapp/conversations/{conv_id}/messages?mark_read=true")
    assert response.status_code == 200

    data = response.get_json()
    assert len(data["messages"]) == 1
    assert data["conversation"]["unreadCount"] == 0
    assert data["conversation"]["contact"]["displayName"] == "Kansal"

    conv_list = client.get("/api/whatsapp/conversations")
    assert conv_list.status_code == 200
    convs = conv_list.get_json()["conversations"]
    assert convs[0]["unreadCount"] == 0


def test_inbound_webhook_is_idempotent_and_inherits_lane(client) -> None:
    conv_id, _ = _seed_thread()
    lane_id = uuid.uuid4()
    with db_base.session_scope() as db:
        conv = db.query(MessagingConversation).filter_by(id=uuid.UUID(conv_id)).one()
        db.add(MessagingMessage(
            id=uuid.uuid4(),
            conversation_id=conv.id,
            contact_id=conv.contact_id,
            lane_id=lane_id,
            carrier_name="Kansal",
            source_type="manual",
            direction="outbound",
            body="[template: spot_bid]",
            provider="meta_whatsapp",
            provider_message_id="wamid.outbound.1",
            status="sent",
            is_template=True,
            template_name="spot_bid",
            sent_at=_now(),
            created_at=_now(),
        ))
        db.commit()

    value = {
        "contacts": [{"profile": {"name": "Kansal"}, "wa_id": "18057332428"}],
        "messages": [{
            "from": "18057332428",
            "id": "wamid.inbound.1",
            "timestamp": str(int(_now().timestamp())),
            "type": "text",
            "text": {"body": "We can cover it."},
        }],
    }
    with db_base.session_scope() as db:
        ingest_inbound_message(db, value)
    with db_base.session_scope() as db:
        ingest_inbound_message(db, value)

    with db_base.session_scope() as db:
        inbound = db.query(MessagingMessage).filter_by(provider_message_id="wamid.inbound.1").all()
        assert len(inbound) == 1
        assert inbound[0].lane_id == lane_id
        assert inbound[0].source_type == "manual"
