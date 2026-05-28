import { useMemo, useState } from "react";
import { useLanes } from "../api/portalApi";
import ActiveLanesWorkspace, {
  type LaneUiStatus,
} from "../components/portal/ActiveLanesWorkspace";
import CarrierCRMView from "../components/portal/CarrierCRMView";
import LaneDetailPanel from "../components/portal/LaneDetailPanel";
import LaneIntakeForm from "../components/portal/LaneIntakeForm";
import { useCarrierCRM } from "../api/portalApi";

type LeftTab = "active_lanes" | "completed_lanes" | "carrier_crm";

function inferStatus(statusRaw: string): LaneUiStatus {
  if (statusRaw === "closed") return "completed";
  return "active";
}

export default function PortalPage() {
  const [leftTab, setLeftTab] = useState<LeftTab>("active_lanes");
  const [selectedLaneId, setSelectedLaneId] = useState<string | null>(null);
  const [showCreateLane, setShowCreateLane] = useState(false);
  const [statusOverrides, setStatusOverrides] = useState<Record<string, LaneUiStatus>>({});

  const { data: lanesData } = useLanes();
  const lanes = lanesData?.lanes ?? [];

  const effectiveLaneId = useMemo(() => {
    if (selectedLaneId) return selectedLaneId;
    return lanes[0]?.lane_id ?? null;
  }, [selectedLaneId, lanes]);

  const { data: crmData, isLoading: crmLoading } = useCarrierCRM(
    leftTab === "carrier_crm" ? effectiveLaneId : null
  );

  function handleCreated(laneId: string) {
    setSelectedLaneId(laneId);
    setShowCreateLane(false);
    setLeftTab("active_lanes");
  }

  function laneStatus(laneId: string): LaneUiStatus {
    const lane = lanes.find((item) => item.lane_id === laneId);
    if (!lane) return "active";
    return statusOverrides[laneId] ?? inferStatus(lane.status);
  }

  return (
    <div className="portal-shell">
      <aside className="left-nav">
        <div className="brand">
          <div className="brand-mark">SB</div>
          <div>
            <div className="brand-title">Spot Bid Portal</div>
            <div className="brand-subtitle">Lane operations console</div>
          </div>
        </div>

        <nav className="left-tabs">
          <button
            className={`left-tab ${leftTab === "active_lanes" ? "active" : ""}`}
            onClick={() => setLeftTab("active_lanes")}
          >
            Active Lanes
          </button>
          <button
            className={`left-tab ${leftTab === "completed_lanes" ? "active" : ""}`}
            onClick={() => setLeftTab("completed_lanes")}
          >
            Completed
          </button>
          <button
            className={`left-tab ${leftTab === "carrier_crm" ? "active" : ""}`}
            onClick={() => setLeftTab("carrier_crm")}
          >
            Carrier CRM
          </button>
        </nav>
      </aside>

      <main className="content-area">
        {(leftTab === "active_lanes" || leftTab === "completed_lanes") && (
          <ActiveLanesWorkspace
            selectedLaneId={selectedLaneId}
            onSelectLane={setSelectedLaneId}
            onNewLane={() => setShowCreateLane(true)}
            laneTab={leftTab === "active_lanes" ? "active" : "completed"}
            statusOverrides={statusOverrides}
          />
        )}

        {leftTab === "carrier_crm" && (
          <section className="lanes-workspace">
            <header className="workspace-header">
              <div>
                <h1>Carrier CRM</h1>
                <p>Carrier profile history and communication preferences.</p>
              </div>
            </header>
            {crmLoading && (
              <div>
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="skeleton skeleton-row" />
                ))}
              </div>
            )}
            {!crmLoading && crmData && <CarrierCRMView carriers={crmData.carriers} />}
            {!crmLoading && !crmData && (
              <div className="table-empty">Create/select a lane to preview carrier profiles.</div>
            )}
          </section>
        )}
      </main>

      {selectedLaneId && leftTab !== "carrier_crm" && (
        <section className="detail-drawer">
          <div className="detail-drawer-head">
            <button
              className="drawer-close"
              onClick={() => setSelectedLaneId(null)}
              aria-label="Close lane detail"
            >
              ×
            </button>
          </div>
          <LaneDetailPanel
            laneId={selectedLaneId}
            status={laneStatus(selectedLaneId)}
            onStatusChange={(next) => {
              setStatusOverrides((prev) => ({ ...prev, [selectedLaneId]: next }));
              if (next === "completed") setLeftTab("completed_lanes");
              if (next === "active") setLeftTab("active_lanes");
            }}
          />
        </section>
      )}

      {showCreateLane && (
        <div className="modal-backdrop" onClick={() => setShowCreateLane(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <LaneIntakeForm
              onCreated={handleCreated}
              onCancel={() => setShowCreateLane(false)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
