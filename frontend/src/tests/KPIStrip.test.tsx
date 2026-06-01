import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import KPIStrip from "../components/portal/KPIStrip";
import type { MetricsSnapshot } from "../types/portal";

const METRICS: MetricsSnapshot = {
  carriers_contacted: 25,
  carriers_responded: 14,
  emails_sent: 18,
  emails_clicked: 7,
  email_replies: 4,
  sms_sent: 15,
  sms_replies: 5,
  whatsapp_sent: 10,
  whatsapp_replies: 3,
};

describe("KPIStrip", () => {
  it("renders all 9 tile labels", () => {
    render(<KPIStrip metrics={METRICS} />);
    expect(screen.getByText("Carriers Contacted")).toBeInTheDocument();
    expect(screen.getByText("Carriers Responded")).toBeInTheDocument();
    expect(screen.getByText("Emails Sent")).toBeInTheDocument();
    expect(screen.getByText("Emails Clicked")).toBeInTheDocument();
    expect(screen.getByText("Email Replies")).toBeInTheDocument();
    expect(screen.getByText("SMS Sent")).toBeInTheDocument();
    expect(screen.getByText("SMS Replies")).toBeInTheDocument();
    expect(screen.getByText("WhatsApp Sent")).toBeInTheDocument();
    expect(screen.getByText("WhatsApp Replies")).toBeInTheDocument();
  });

  it("renders correct values", () => {
    render(<KPIStrip metrics={METRICS} />);
    expect(screen.getByText("25")).toBeInTheDocument();
    expect(screen.getByText("14")).toBeInTheDocument();
    expect(screen.getByText("18")).toBeInTheDocument();
  });

  it("renders 9 tiles", () => {
    render(<KPIStrip metrics={METRICS} />);
    const strip = screen.getByTestId("kpi-strip");
    expect(strip.querySelectorAll(".kpi-tile")).toHaveLength(9);
  });
});
