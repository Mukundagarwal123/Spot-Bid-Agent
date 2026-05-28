import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import LaneCard from "../components/portal/LaneCard";
import type { LaneSummary } from "../types/portal";

const LANE: LaneSummary = {
  lane_id: "abc-123",
  label: "Chicago, IL → Dallas, TX",
  equipment_type: "dry_van",
  status: "new",
  last_activity_at: "2025-06-01T12:00:00",
  pickup_date: null,
  metrics_preview: { carriers_contacted: 20, carriers_responded: 12 },
};

describe("LaneCard", () => {
  it("renders the lane label", () => {
    render(<LaneCard lane={LANE} isActive={false} onClick={() => {}} />);
    expect(screen.getByText("Chicago, IL → Dallas, TX")).toBeInTheDocument();
  });

  it("renders the status badge", () => {
    render(<LaneCard lane={LANE} isActive={false} onClick={() => {}} />);
    expect(screen.getByText("new")).toBeInTheDocument();
  });

  it("renders the equipment type label", () => {
    render(<LaneCard lane={LANE} isActive={false} onClick={() => {}} />);
    expect(screen.getByText("Dry Van")).toBeInTheDocument();
  });

  it("renders metrics preview", () => {
    render(<LaneCard lane={LANE} isActive={false} onClick={() => {}} />);
    expect(screen.getByText(/20 contacted/)).toBeInTheDocument();
    expect(screen.getByText(/12 responded/)).toBeInTheDocument();
  });

  it("applies active class when isActive is true", () => {
    render(<LaneCard lane={LANE} isActive={true} onClick={() => {}} />);
    const card = screen.getByTestId("lane-card");
    expect(card.className).toContain("active");
  });

  it("does not apply active class when isActive is false", () => {
    render(<LaneCard lane={LANE} isActive={false} onClick={() => {}} />);
    const card = screen.getByTestId("lane-card");
    expect(card.className).not.toContain("active");
  });
});
