import type { TimelineEvent } from "../../types/portal";

interface Props {
  events: TimelineEvent[];
}

function fmtTime(dt: string) {
  return new Date(dt).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ActivityTimeline({ events }: Props) {
  return (
    <div className="timeline">
      <h3>Activity Timeline</h3>
      <ul className="timeline-list">
        {events.map((e, i) => (
          <li className="timeline-item" key={i}>
            <div className="timeline-dot" />
            <div className="timeline-content">
              <div className="timeline-label">{e.label}</div>
              <div className="timeline-time">{fmtTime(e.timestamp)}</div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
