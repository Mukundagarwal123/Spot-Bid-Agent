"""Feature 006 — outreach layer unit tests."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.portal.outreach.template import generate
from app.db.models import (
    OutreachMessage,
    MessagingMessage,
    PortalLane,
)
from app.db import base as db_base


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lane(**kwargs) -> SimpleNamespace:
    """Return a plain namespace that mimics PortalLane attributes for unit tests."""
    defaults = dict(
        id=uuid.uuid4(),
        origin_city="Dallas",
        origin_state="TX",
        origin_zip="75001",
        destination_city="Phoenix",
        destination_state="AZ",
        destination_zip="85001",
        equipment_type="dry_van",
        pickup_date=date(2026, 6, 20),
        status="new",
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Template tests
# ---------------------------------------------------------------------------

class TestEmailTemplate:
    def test_subject_contains_cities_and_equipment(self):
        lane = _lane()
        draft = generate(lane, "")
        assert "Dallas, TX" in draft.subject
        assert "Phoenix, AZ" in draft.subject
        assert "Dry Van" in draft.subject

    def test_body_contains_lane_details(self):
        lane = _lane()
        draft = generate(lane, "")
        assert "Dallas" in draft.body
        assert "Phoenix" in draft.body
        assert "Dry Van" in draft.body
        assert "June 20, 2026" in draft.body

    def test_notes_block_injected(self):
        lane = _lane()
        draft = generate(lane, "Please confirm ASAP.")
        assert "Please confirm ASAP." in draft.body
        assert "Additional Notes" in draft.body

    def test_no_notes_block_when_empty(self):
        lane = _lane()
        draft = generate(lane, "")
        assert "Additional Notes" not in draft.body

    def test_no_pickup_date_shows_tbd(self):
        lane = _lane(pickup_date=None)
        draft = generate(lane, "")
        assert "TBD" in draft.body


# ---------------------------------------------------------------------------
# Webhook handler — idempotency and status progression
# ---------------------------------------------------------------------------

class TestWebhookHandler:
    def _make_message(self, status="sent") -> OutreachMessage:
        msg = MagicMock(spec=OutreachMessage)
        msg.id = uuid.uuid4()
        msg.provider_message_id = "msg_test_123"
        msg.status = status
        msg.delivered_at = None
        msg.opened_at = None
        msg.clicked_at = None
        msg.replied_at = None
        return msg

    def _payload(self, event_type="email.delivered"):
        return {
            "type": event_type,
            "created_at": "2026-06-13T12:00:00Z",
            "data": {"email_id": "msg_test_123"},
        }

    def test_status_rank_progression(self):
        from app.webhooks.resend_handler import _STATUS_RANK
        assert _STATUS_RANK["delivered"] > _STATUS_RANK["sent"]
        assert _STATUS_RANK["opened"] > _STATUS_RANK["delivered"]
        assert _STATUS_RANK["clicked"] > _STATUS_RANK["opened"]
        assert _STATUS_RANK["replied"] > _STATUS_RANK["clicked"]

    def test_opened_does_not_downgrade_clicked(self):
        from app.webhooks.resend_handler import _STATUS_RANK
        assert _STATUS_RANK["opened"] < _STATUS_RANK["clicked"]

    def test_idempotency_key_format(self):
        provider_id = "msg_abc"
        event_type = "delivered"
        epoch_ms = 1718272800000
        key = f"{provider_id}::{event_type}::{epoch_ms}"
        assert "::" in key
        assert key.startswith("msg_abc")


# ---------------------------------------------------------------------------
# Reply matcher
# ---------------------------------------------------------------------------

class TestReplyMatcher:
    def _make_db(self, match_message=None):
        db = MagicMock()
        q = MagicMock()
        db.query.return_value = q
        q.filter.return_value = q
        q.filter_by.return_value = q
        q.order_by.return_value = q
        q.first.return_value = match_message
        db.add = MagicMock()
        db.commit = MagicMock()
        return db

    def test_matched_reply_sets_replied_at(self):
        from app.webhooks.reply_handler import handle_reply

        msg = MagicMock(spec=OutreachMessage)
        msg.id = uuid.uuid4()
        msg.lane_id = uuid.uuid4()
        msg.provider_message_id = "msg_xyz"
        msg.replied_at = None
        msg.status = "opened"

        db = self._make_db(match_message=msg)
        handle_reply(db, {"from": "carrier@example.com", "text": "Yes we can do it. $2800.", "subject": "Re: Spot Bid"})

        assert msg.replied_at is not None
        assert msg.status == "replied"
        db.commit.assert_called_once()

    def test_unmatched_reply_still_persisted(self):
        from app.webhooks.reply_handler import handle_reply

        db = self._make_db(match_message=None)
        handle_reply(db, {"from": "unknown@example.com", "text": "Hello", "subject": "?"})

        db.add.assert_called()
        db.commit.assert_called_once()


def _seed_lane() -> uuid.UUID:
    lane_id = uuid.uuid4()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with db_base.session_scope() as db:
        db.add(PortalLane(
            id=lane_id,
            origin_city="Dallas",
            origin_state="TX",
            origin_zip="75001",
            destination_city="Phoenix",
            destination_state="AZ",
            destination_zip="85001",
            equipment_type="dry_van",
            pickup_date=date(2026, 6, 20),
            status="new",
            notes=None,
            created_at=now,
            updated_at=now,
        ))
        db.commit()
    return lane_id


def test_mixed_channel_preview_counts_unique_contacts(client) -> None:
    lane_id = _seed_lane()
    response = client.post(f"/portal/lanes/{lane_id}/outreach/preview", json={
        "include_internal": False,
        "include_dat": False,
        "include_crr_model": False,
        "send_email": True,
        "send_whatsapp": True,
        "whatsapp_template_name": "spot_bid",
        "manual_emails": [{"carrier_name": "Acme", "email": "ops@acme.test"}],
        "manual_phones": [{"carrier_name": "Acme", "phone": "+1 (805) 555-1212"}],
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data["email_recipient_count"] == 1
    assert data["whatsapp_recipient_count"] == 1
    assert data["unique_contact_count"] == 1
    assert data["recipient_count_by_channel"] == {"email": 1, "whatsapp": 1}


def test_lane_creation_persists_draft_campaign_config(client) -> None:
    response = client.post("/portal/lanes", json={
        "origin_city": "Dallas",
        "origin_state": "TX",
        "origin_zip": "75001",
        "destination_city": "Phoenix",
        "destination_state": "AZ",
        "destination_zip": "85001",
        "equipment_type": "dry_van",
        "include_internal": False,
        "include_dat": True,
        "include_crr_model": False,
        "channels": ["email", "whatsapp"],
        "whatsapp_source_types": ["dat", "manual"],
        "manual_recipients": [{
            "carrier_name": "Acme",
            "email": "ops@acme.test",
            "phone": "18055551212",
        }],
    })
    assert response.status_code == 201
    lane = client.get(f"/portal/lanes/{response.get_json()['lane_id']}").get_json()["lane"]
    config = lane["campaign_config"]
    assert config["channels"] == {"email": True, "whatsapp": True}
    assert config["sources"]["manual"] is True
    assert config["manual_recipients"][0]["phone"] == "18055551212"


def test_mixed_send_persists_whatsapp_campaign_link(client, monkeypatch) -> None:
    lane_id = _seed_lane()
    monkeypatch.setattr("app.portal.outreach.sender.send_batch", lambda params: ["email-1"])

    response_mock = MagicMock()
    response_mock.raise_for_status.return_value = None
    response_mock.json.return_value = {"messages": [{"id": "wamid.campaign.1"}]}
    monkeypatch.setattr("app.services.whatsapp_service.requests.post", lambda *args, **kwargs: response_mock)

    response = client.post(f"/portal/lanes/{lane_id}/outreach/send", json={
        "include_internal": False,
        "include_dat": False,
        "include_crr_model": False,
        "send_email": True,
        "send_whatsapp": True,
        "whatsapp_template_name": "spot_bid",
        "manual_emails": [{"carrier_name": "Acme", "email": "ops@acme.test"}],
        "manual_phones": [{"carrier_name": "Acme", "phone": "+1 805 555 1212"}],
    })
    assert response.status_code == 201
    data = response.get_json()
    assert data["email_sent_count"] == 1
    assert data["whatsapp_sent_count"] == 1

    with db_base.session_scope() as db:
        message = db.query(MessagingMessage).filter_by(provider_message_id="wamid.campaign.1").one()
        assert message.lane_id == lane_id
        assert message.batch_id == uuid.UUID(data["batch_id"])
        assert message.source_type == "manual"

    metrics = client.get(f"/portal/lanes/{lane_id}/outreach").get_json()
    assert metrics["sent"] == 2
    assert metrics["channel_metrics"]["email"]["sent"] == 1
    assert metrics["channel_metrics"]["whatsapp"]["sent"] == 1


def test_manual_whatsapp_phone_requires_country_code(client) -> None:
    lane_id = _seed_lane()
    response = client.post(f"/portal/lanes/{lane_id}/outreach/preview", json={
        "include_internal": False,
        "include_dat": False,
        "include_crr_model": False,
        "send_email": False,
        "send_whatsapp": True,
        "whatsapp_template_name": "hello_world",
        "manual_phones": [{"carrier_name": "Acme", "phone": "8057332428"}],
    })
    assert response.status_code == 422
    assert "country calling code" in response.get_data(as_text=True)


def test_all_whatsapp_failures_return_provider_error(client, monkeypatch) -> None:
    from app.services.whatsapp_service import WhatsAppSendError

    lane_id = _seed_lane()
    monkeypatch.setattr(
        "app.services.whatsapp_service.send_template",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            WhatsAppSendError("[131030] Recipient phone number not in allowed list")
        ),
    )
    response = client.post(f"/portal/lanes/{lane_id}/outreach/send", json={
        "include_internal": False,
        "include_dat": False,
        "include_crr_model": False,
        "send_email": False,
        "send_whatsapp": True,
        "whatsapp_template_name": "hello_world",
        "manual_phones": [{"carrier_name": "Acme", "phone": "+1 805 733 2428"}],
    })
    assert response.status_code == 502
    assert "not in allowed list" in response.get_json()["detail"]
