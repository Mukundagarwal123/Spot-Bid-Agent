import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import CarrierCRMView from "../components/portal/CarrierCRMView";
import type { CarrierCRMItem } from "../types/portal";

const CARRIERS: CarrierCRMItem[] = [
  {
    carrier_name: "Swift Transport LLC",
    times_contacted: 5,
    times_responded: 4,
    avg_response_time_minutes: 45,
    preferred_channel: "email",
    response_rate: 80.0,
    last_contacted_at: "2025-05-01T10:00:00",
  },
  {
    carrier_name: "Apex Freight Inc",
    times_contacted: 3,
    times_responded: 1,
    avg_response_time_minutes: 120,
    preferred_channel: "sms",
    response_rate: 33.33,
    last_contacted_at: "2025-04-15T08:00:00",
  },
];

describe("CarrierCRMView", () => {
  it("renders the correct row count in the header", () => {
    render(<CarrierCRMView carriers={CARRIERS} />);
    expect(screen.getByText(/2 carriers/)).toBeInTheDocument();
  });

  it("renders all carrier names", () => {
    render(<CarrierCRMView carriers={CARRIERS} />);
    expect(screen.getByText("Swift Transport LLC")).toBeInTheDocument();
    expect(screen.getByText("Apex Freight Inc")).toBeInTheDocument();
  });

  it("renders response rate formatted with %", () => {
    render(<CarrierCRMView carriers={CARRIERS} />);
    expect(screen.getByText("80.0%")).toBeInTheDocument();
    expect(screen.getByText("33.3%")).toBeInTheDocument();
  });

  it("renders preferred channel chips", () => {
    render(<CarrierCRMView carriers={CARRIERS} />);
    const chips = screen.getByTestId("crm-view").querySelectorAll(".channel-chip");
    expect(chips.length).toBeGreaterThan(0);
  });

  it("renders table rows for each carrier", () => {
    render(<CarrierCRMView carriers={CARRIERS} />);
    const rows = screen.getByTestId("crm-view").querySelectorAll("tbody tr");
    expect(rows).toHaveLength(2);
  });
});
