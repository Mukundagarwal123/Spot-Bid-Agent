import type { MetricsSnapshot } from "../../types/portal";

interface Row {
  channel: string;
  sent: number;
  replies: number;
  replyRate: number;
  clicks?: number;
}

function buildRows(m: MetricsSnapshot): Row[] {
  const rows: Row[] = [
    {
      channel: "email",
      sent: m.emails_sent,
      replies: m.email_replies,
      clicks: m.emails_clicked,
      replyRate: m.emails_sent > 0 ? Math.round((m.email_replies / m.emails_sent) * 100) : 0,
    },
    {
      channel: "sms",
      sent: m.sms_sent,
      replies: m.sms_replies,
      replyRate: m.sms_sent > 0 ? Math.round((m.sms_replies / m.sms_sent) * 100) : 0,
    },
    {
      channel: "whatsapp",
      sent: m.whatsapp_sent,
      replies: m.whatsapp_replies,
      replyRate: m.whatsapp_sent > 0 ? Math.round((m.whatsapp_replies / m.whatsapp_sent) * 100) : 0,
    },
  ];
  return rows;
}

interface Props {
  metrics: MetricsSnapshot;
}

export default function ChannelBreakdownTable({ metrics }: Props) {
  const rows = buildRows(metrics);
  const totalSent = rows.reduce((acc, row) => acc + row.sent, 0);
  const totalReplies = rows.reduce((acc, row) => acc + row.replies, 0);
  const bestChannel = [...rows].sort((a, b) => b.replyRate - a.replyRate)[0]?.channel ?? "-";

  return (
    <div className="channel-table">
      <div className="channel-header">
        <h3>Channel Overview</h3>
        <div className="channel-summary">
          <span>Total Sent: {totalSent}</span>
          <span>Total Replies: {totalReplies}</span>
          <span>Best Channel: {bestChannel}</span>
        </div>
      </div>

      <div className="channel-cards">
        {rows.map((row) => (
          <div className="channel-card" key={row.channel}>
            <div className="channel-card-top">
              <span className={`channel-chip ${row.channel}`}>{row.channel}</span>
              <strong>{row.replyRate}%</strong>
            </div>
            <div className="channel-metrics">
              <div>
                <span>Sent</span>
                <strong>{row.sent}</strong>
              </div>
              <div>
                <span>Replies</span>
                <strong>{row.replies}</strong>
              </div>
              {typeof row.clicks === "number" && (
                <div>
                  <span>Clicks</span>
                  <strong>{row.clicks}</strong>
                </div>
              )}
            </div>
            <div className="rate-track">
              <div className="rate-fill" style={{ width: `${row.replyRate}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
