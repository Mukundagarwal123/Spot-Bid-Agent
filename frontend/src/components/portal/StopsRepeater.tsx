import type { StopInput } from "../../types/portal";

interface Props {
  stops: StopInput[];
  onAdd: () => void;
  onRemove: (index: number) => void;
  onChange: (index: number, field: keyof StopInput, value: string) => void;
}

export default function StopsRepeater({ stops, onAdd, onRemove, onChange }: Props) {
  return (
    <div>
      <div className="section-label">Intermediate Stops (optional)</div>
      {stops.length > 0 && (
        <div className="stops-list">
          {stops.map((stop, i) => (
            <div className="stop-row" key={i}>
              <div className="form-field">
                {i === 0 && <label>City *</label>}
                <input
                  value={stop.city}
                  placeholder="City"
                  onChange={(e) => onChange(i, "city", e.target.value)}
                  aria-label={`Stop ${i + 1} city`}
                />
              </div>
              <div className="form-field">
                {i === 0 && <label>State *</label>}
                <input
                  value={stop.state}
                  maxLength={2}
                  placeholder="ST"
                  onChange={(e) =>
                    onChange(i, "state", e.target.value.toUpperCase())
                  }
                  aria-label={`Stop ${i + 1} state`}
                />
              </div>
              <div className="form-field">
                {i === 0 && <label>ZIP</label>}
                <input
                  value={stop.zip ?? ""}
                  maxLength={5}
                  placeholder="ZIP"
                  onChange={(e) => onChange(i, "zip", e.target.value)}
                  aria-label={`Stop ${i + 1} zip`}
                />
              </div>
              <button
                type="button"
                className="btn-remove-stop"
                onClick={() => onRemove(i)}
                aria-label={`Remove stop ${i + 1}`}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
      <button type="button" className="btn-add-stop" onClick={onAdd}>
        + Add Stop
      </button>
    </div>
  );
}
