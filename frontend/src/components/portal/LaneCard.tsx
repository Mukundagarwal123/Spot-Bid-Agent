import type { LaneSummary } from "../../types/portal";
import { EQUIPMENT_LABELS } from "../../types/portal";

interface Props {
  lane: LaneSummary;
  isActive: boolean;
  onClick: () => void;
}

function fmt(dt: string) {
  return new Date(dt).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function LaneCard({ lane, isActive, onClick }: Props) {
  return (
    <div
      className={`lane-card${isActive ? " active" : ""}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      data-testid="lane-card"
    >
      <div className="lane-card-label" title={lane.label}>
        {lane.label}
      </div>
      <div className="lane-card-meta">
        <span className={`lane-status-badge ${lane.status}`}>{lane.status}</span>
        <span className="lane-card-equip">
          {EQUIPMENT_LABELS[lane.equipment_type] ?? lane.equipment_type}
        </span>
      </div>
      <div className="lane-card-preview">
        {lane.metrics_preview.carriers_contacted} contacted |{" "}
        {lane.metrics_preview.carriers_responded} responded
      </div>
      <div className="lane-card-preview">{fmt(lane.last_activity_at)}</div>
    </div>
  );
}
