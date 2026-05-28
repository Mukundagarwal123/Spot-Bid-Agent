import { useLanes } from "../../api/portalApi";
import LaneCard from "./LaneCard";

interface Props {
  selectedLaneId: string | null;
  onSelect: (laneId: string) => void;
  onNewLane: () => void;
}

export default function ActiveLanesBoard({ selectedLaneId, onSelect, onNewLane }: Props) {
  const { data, isLoading } = useLanes();

  return (
    <div className="lanes-board">
      <div className="lanes-board-header">
        <h3>Active Lanes</h3>
        <button className="lanes-board-btn" onClick={onNewLane}>
          + New
        </button>
      </div>

      <div className="lanes-list">
        {isLoading && (
          <div style={{ padding: "16px" }}>
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton skeleton-row" style={{ marginBottom: 12 }} />
            ))}
          </div>
        )}

        {!isLoading && (!data || data.lanes.length === 0) && (
          <div className="lanes-empty">
            <p>No lanes yet.</p>
            <button className="btn-primary" onClick={onNewLane}>
              Create your first lane
            </button>
          </div>
        )}

        {!isLoading &&
          data?.lanes.map((lane) => (
            <LaneCard
              key={lane.lane_id}
              lane={lane}
              isActive={lane.lane_id === selectedLaneId}
              onClick={() => onSelect(lane.lane_id)}
            />
          ))}
      </div>
    </div>
  );
}
