import type { MetricsSnapshot } from "../../types/portal";

interface Tile {
  label: string;
  value: number;
}

function tiles(m: MetricsSnapshot): Tile[] {
  return [
    { label: "Carriers Contacted", value: m.carriers_contacted },
    { label: "Carriers Responded", value: m.carriers_responded },
    { label: "Emails Sent", value: m.emails_sent },
    { label: "Emails Clicked", value: m.emails_clicked },
    { label: "Email Replies", value: m.email_replies },
    { label: "SMS Sent", value: m.sms_sent },
    { label: "SMS Replies", value: m.sms_replies },
    { label: "WhatsApp Sent", value: m.whatsapp_sent },
    { label: "WhatsApp Replies", value: m.whatsapp_replies },
  ];
}

interface Props {
  metrics: MetricsSnapshot;
}

export default function KPIStrip({ metrics }: Props) {
  return (
    <div className="kpi-strip" data-testid="kpi-strip">
      {tiles(metrics).map((t) => (
        <div className="kpi-tile" key={t.label}>
          <div className="kpi-tile-value">{t.value}</div>
          <div className="kpi-tile-label">{t.label}</div>
        </div>
      ))}
    </div>
  );
}
