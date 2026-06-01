import { useEffect, useMemo, useState } from "react";
import { useCarrierCRM, useLaneDetail } from "../../api/portalApi";
import ActivityTimeline from "./ActivityTimeline";
import ChannelBreakdownTable from "./ChannelBreakdownTable";
import type { LaneUiStatus } from "./ActiveLanesWorkspace";
import type { CarrierCRMItem } from "../../types/portal";

interface Props {
  laneId: string;
  status: LaneUiStatus;
  onStatusChange: (status: LaneUiStatus) => void;
}

type Tab = "overview" | "responses" | "activity";

function fmtDate(dt: string) {
  return new Date(dt).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface ChatMessage {
  from: "agent" | "carrier";
  channel: string;
  text: string;
  at: string;
}

function buildDummyConversation(carrier: CarrierCRMItem): ChatMessage[] {
  const c = carrier.preferred_channel;
  return [
    {
      from: "agent",
      channel: c,
      text: "Hi, we have a lane available. Can you quote this today?",
      at: carrier.last_contacted_at,
    },
    {
      from: "carrier",
      channel: c,
      text: "Yes, share pickup window and target rate.",
      at: carrier.last_contacted_at,
    },
    {
      from: "agent",
      channel: c,
      text: "Pickup tomorrow morning. Sending details now.",
      at: carrier.last_contacted_at,
    },
  ];
}

function buildCarrierDetails(carrier: CarrierCRMItem) {
  const seed = carrier.carrier_name
    .split("")
    .reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
  const local = carrier.carrier_name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ".")
    .replace(/^\.+|\.+$/g, "");
  return {
    mcNumber: `MC-${100000 + (seed % 900000)}`,
    email: `${local || "carrier"}@fleetmail.com`,
    phone: `+1 (5${(seed % 10) + 1}5) ${100 + (seed % 800)}-${1000 + (seed % 8999)}`,
  };
}

type ChannelFilter = "all" | "email" | "sms" | "whatsapp";

function CarrierResponsesBlock({ carriers }: { carriers: CarrierCRMItem[] }) {
  const [channelFilter, setChannelFilter] = useState<ChannelFilter>("all");
  const respondedCarriers = useMemo(
    () =>
      carriers.filter(
        (c) =>
          c.times_responded > 0 &&
          (channelFilter === "all" || c.preferred_channel === channelFilter)
      ),
    [carriers, channelFilter]
  );
  const [selectedCarrier, setSelectedCarrier] = useState<CarrierCRMItem | null>(
    respondedCarriers[0] ?? null
  );
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    if (!respondedCarriers.length) {
      setSelectedCarrier(null);
      return;
    }
    if (!selectedCarrier) {
      setSelectedCarrier(respondedCarriers[0]);
      return;
    }
    const stillVisible = respondedCarriers.some(
      (c) => c.carrier_name === selectedCarrier.carrier_name
    );
    if (!stillVisible) setSelectedCarrier(respondedCarriers[0]);
  }, [respondedCarriers, selectedCarrier]);

  if (respondedCarriers.length === 0) {
    return (
      <div>
        <div className="response-toolbar">
          <span>Filter by channel:</span>
          {(["all", "email", "sms", "whatsapp"] as ChannelFilter[]).map((item) => (
            <button
              key={item}
              className={`filter-chip ${channelFilter === item ? "active" : ""}`}
              onClick={() => setChannelFilter(item)}
            >
              {item}
            </button>
          ))}
        </div>
        <div className="table-empty">No carrier responses for selected channel.</div>
      </div>
    );
  }

  const messages = selectedCarrier ? buildDummyConversation(selectedCarrier) : [];
  const details = selectedCarrier ? buildCarrierDetails(selectedCarrier) : null;

  return (
    <div className="responses-layout">
      <div className="responses-list">
        <div className="response-toolbar">
          <span>Responded Carriers</span>
          <div className="filter-chip-row">
            {(["all", "email", "sms", "whatsapp"] as ChannelFilter[]).map((item) => (
              <button
                key={item}
                className={`filter-chip ${channelFilter === item ? "active" : ""}`}
                onClick={() => setChannelFilter(item)}
              >
                {item}
              </button>
            ))}
          </div>
        </div>
        {respondedCarriers.map((carrier) => (
          <button
            key={carrier.carrier_name}
            className={`response-item${
              selectedCarrier?.carrier_name === carrier.carrier_name ? " active" : ""
            }`}
            onClick={() => setSelectedCarrier(carrier)}
          >
            <div>
              <div className="response-carrier">{carrier.carrier_name}</div>
              <div className="response-meta">
                {carrier.times_responded} responses | {carrier.response_rate.toFixed(1)}%
              </div>
            </div>
            <span className={`channel-chip ${carrier.preferred_channel}`}>
              {carrier.preferred_channel}
            </span>
          </button>
        ))}
      </div>

      <div className="conversation-panel">
        <h4>Communication History</h4>
        {selectedCarrier && (
          <>
            <div className="conversation-header">
              <strong>{selectedCarrier.carrier_name}</strong>
              <div className="conversation-header-actions">
                <span>Last contact: {fmtDate(selectedCarrier.last_contacted_at)}</span>
                <button
                  className="details-toggle"
                  onClick={() => setShowDetails((prev) => !prev)}
                >
                  {showDetails ? "Hide Details" : "Carrier Details"}
                </button>
              </div>
            </div>
            {showDetails && details && (
              <div className="carrier-details-card">
                <div>
                  <span className="details-label">MC Number</span>
                  <strong>{details.mcNumber}</strong>
                </div>
                <div>
                  <span className="details-label">Email</span>
                  <strong>{details.email}</strong>
                </div>
                <div>
                  <span className="details-label">Contact</span>
                  <strong>{details.phone}</strong>
                </div>
              </div>
            )}
            <div className="chat-thread">
              {messages.map((msg, idx) => (
                <div
                  key={`${msg.from}-${idx}`}
                  className={`chat-bubble ${msg.from === "agent" ? "agent" : "carrier"}`}
                >
                  <div className="chat-top">
                    <span>{msg.from === "agent" ? "Agent" : "Carrier"}</span>
                    <span>{msg.channel}</span>
                  </div>
                  <p>{msg.text}</p>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function LaneDetailPanel({ laneId, status, onStatusChange }: Props) {
  const [tab, setTab] = useState<Tab>("overview");
  const { data: detail, isLoading: detailLoading } = useLaneDetail(laneId);
  const { data: crm, isLoading: crmLoading } = useCarrierCRM(laneId);

  if (detailLoading || !detail) {
    return (
      <div className="lane-detail">
        <div className="skeleton skeleton-row" style={{ height: 130 }} />
        <div className="skeleton skeleton-row" style={{ height: 200 }} />
      </div>
    );
  }

  return (
    <div className="lane-detail">
      <div className="lane-detail-header">
        <div>
          <h1 className="lane-detail-title">{detail.lane.label}</h1>
          <p className="lane-detail-subtitle">
            {detail.lane.equipment_type.replace("_", " ")}
            {detail.lane.pickup_date ? ` | Pickup ${detail.lane.pickup_date}` : ""}
            {detail.stops.length > 0
              ? ` | ${detail.stops.length} stop${detail.stops.length > 1 ? "s" : ""}`
              : ""}
          </p>
        </div>
        <div className="lane-header-actions">
          <span className={`lane-status-badge ${status}`}>{status}</span>
          <select
            className="status-select"
            value={status}
            onChange={(e) => onStatusChange(e.target.value as LaneUiStatus)}
          >
            <option value="active">Active</option>
            <option value="completed">Completed</option>
          </select>
        </div>
      </div>

      {detail.stops.length > 0 && (
        <div className="stops-strip">
          {detail.stops.map((stop) => (
            <span key={`${stop.stop_order}-${stop.city}`} className="stop-chip">
              Stop {stop.stop_order}: {stop.city}, {stop.state}
            </span>
          ))}
        </div>
      )}

      <div className="detail-tabs">
        <button
          className={`detail-tab${tab === "overview" ? " active" : ""}`}
          onClick={() => setTab("overview")}
        >
          Overview
        </button>
        <button
          className={`detail-tab${tab === "responses" ? " active" : ""}`}
          onClick={() => setTab("responses")}
        >
          Carrier Responses
        </button>
        <button
          className={`detail-tab${tab === "activity" ? " active" : ""}`}
          onClick={() => setTab("activity")}
        >
          Activity Log
        </button>
      </div>

      {tab === "overview" && (
        <>
          <ChannelBreakdownTable metrics={detail.metrics} />
          {!crmLoading && crm && <CarrierResponsesBlock carriers={crm.carriers} />}
          {crmLoading && <div className="skeleton skeleton-row" style={{ height: 120 }} />}
        </>
      )}

      {tab === "responses" && (
        <div className="responses-panel">
          <h3>Carrier Responses</h3>
          {crmLoading && (
            <div>
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="skeleton skeleton-row" />
              ))}
            </div>
          )}
          {!crmLoading && crm && <CarrierResponsesBlock carriers={crm.carriers} />}
        </div>
      )}

      {tab === "activity" && (
        <div className="responses-panel">
          <h3>Detailed Activity Timeline</h3>
          <ActivityTimeline events={detail.timeline} />
        </div>
      )}
    </div>
  );
}
