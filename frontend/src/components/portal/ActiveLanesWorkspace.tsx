import { useMemo } from "react";
import { useLanes } from "../../api/portalApi";
import { EQUIPMENT_LABELS, type LaneSummary } from "../../types/portal";

export type LaneUiStatus = "active" | "completed";

interface Props {
  selectedLaneId: string | null;
  onSelectLane: (laneId: string) => void;
  onNewLane: () => void;
  laneTab: LaneUiStatus;
  statusOverrides: Record<string, LaneUiStatus>;
}

function fmtDate(dt: string | null) {
  if (!dt) return "-";
  return new Date(dt).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function toUiStatus(
  lane: LaneSummary,
  overrides: Record<string, LaneUiStatus>
): LaneUiStatus {
  if (overrides[lane.lane_id]) return overrides[lane.lane_id];
  if (lane.status === "closed" || lane.status === "completed") return "completed";
  return "active";
}

export default function ActiveLanesWorkspace({
  selectedLaneId,
  onSelectLane,
  onNewLane,
  laneTab,
  statusOverrides,
}: Props) {
  const { data, isLoading } = useLanes();

  const rows = useMemo(
    () =>
      (data?.lanes ?? []).filter(
        (lane) => toUiStatus(lane, statusOverrides) === laneTab
      ),
    [data?.lanes, laneTab, statusOverrides]
  );

  return (
    <section className="lanes-workspace">
      <header className="workspace-header">
        <div>
          <h1>{laneTab === "active" ? "Active Lanes" : "Completed Lanes"}</h1>
          <p>Track outreach and carrier responses by lane.</p>
        </div>
        <button className="btn-primary" onClick={onNewLane}>
          Add Lane
        </button>
      </header>

      <div className="table-wrap">
        <table className="shipment-table">
          <thead>
            <tr>
              <th>Lane</th>
              <th>Equipment</th>
              <th>Pickup Date</th>
              <th>Contacted</th>
              <th>Responded</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {isLoading &&
              Array.from({ length: 5 }).map((_, idx) => (
                <tr key={`sk-${idx}`}>
                  <td colSpan={7}>
                    <div className="skeleton skeleton-row" />
                  </td>
                </tr>
              ))}

            {!isLoading && rows.length === 0 && (
              <tr>
                <td colSpan={7} className="table-empty">
                  No lanes here yet.
                </td>
              </tr>
            )}

            {!isLoading &&
              rows.map((lane) => {
                const status = toUiStatus(lane, statusOverrides);
                const selected = lane.lane_id === selectedLaneId;
                return (
                  <tr
                    key={lane.lane_id}
                    className={selected ? "selected" : ""}
                    onClick={() => onSelectLane(lane.lane_id)}
                  >
                    <td>
                      <div className="lane-title">{lane.label}</div>
                    </td>
                    <td>{EQUIPMENT_LABELS[lane.equipment_type]}</td>
                    <td>{fmtDate(lane.pickup_date)}</td>
                    <td>{lane.metrics_preview.carriers_contacted}</td>
                    <td>{lane.metrics_preview.carriers_responded}</td>
                    <td>
                      <span className={`lane-status-badge ${status}`}>{status}</span>
                    </td>
                    <td>
                      <button
                        className="table-action"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectLane(lane.lane_id);
                        }}
                      >
                        View
                      </button>
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
