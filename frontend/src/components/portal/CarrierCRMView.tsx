import type { CarrierCRMItem } from "../../types/portal";

interface Props {
  carriers: CarrierCRMItem[];
}

function fmtDate(dt: string) {
  return new Date(dt).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "2-digit",
  });
}

export default function CarrierCRMView({ carriers }: Props) {
  return (
    <div className="crm-view" data-testid="crm-view">
      <h3>Carrier CRM ({carriers.length} carriers)</h3>
      <table className="data-table">
        <thead>
          <tr>
            <th>Carrier</th>
            <th>Contacted</th>
            <th>Responded</th>
            <th>Response Rate</th>
            <th>Avg Response</th>
            <th>Preferred Channel</th>
            <th>Last Contacted</th>
          </tr>
        </thead>
        <tbody>
          {carriers.map((c) => (
            <tr key={c.carrier_name}>
              <td style={{ fontWeight: 500 }}>{c.carrier_name}</td>
              <td>{c.times_contacted}</td>
              <td>{c.times_responded}</td>
              <td>{c.response_rate.toFixed(1)}%</td>
              <td>{c.avg_response_time_minutes} min</td>
              <td>
                <span className={`channel-chip ${c.preferred_channel}`}>
                  {c.preferred_channel}
                </span>
              </td>
              <td>{fmtDate(c.last_contacted_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
