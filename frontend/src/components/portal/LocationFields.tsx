interface Props {
  prefix: "origin" | "destination";
  label: string;
  city: string;
  state: string;
  zip: string;
  cityError?: string;
  stateError?: string;
  onChange: (field: string, value: string) => void;
  onBlur: (field: string) => void;
}

export default function LocationFields({
  prefix,
  label,
  city,
  state,
  zip,
  cityError,
  stateError,
  onChange,
  onBlur,
}: Props) {
  return (
    <>
      <div className="section-label">{label}</div>
      <div className="form-row">
        <div className="form-field">
          <label htmlFor={`${prefix}_city`}>{label} City *</label>
          <input
            id={`${prefix}_city`}
            value={city}
            className={cityError ? "error" : ""}
            onChange={(e) => onChange(`${prefix}_city`, e.target.value)}
            onBlur={() => onBlur(`${prefix}_city`)}
            placeholder="e.g. Chicago"
          />
          {cityError && <span className="field-error">{cityError}</span>}
        </div>
        <div className="form-field">
          <label htmlFor={`${prefix}_state`}>{label} State *</label>
          <input
            id={`${prefix}_state`}
            value={state}
            maxLength={2}
            className={stateError ? "error" : ""}
            onChange={(e) =>
              onChange(`${prefix}_state`, e.target.value.toUpperCase())
            }
            onBlur={() => onBlur(`${prefix}_state`)}
            placeholder="IL"
          />
          {stateError && <span className="field-error">{stateError}</span>}
        </div>
        <div className="form-field">
          <label htmlFor={`${prefix}_zip`}>ZIP</label>
          <input
            id={`${prefix}_zip`}
            value={zip}
            maxLength={5}
            onChange={(e) => onChange(`${prefix}_zip`, e.target.value)}
            placeholder="60601"
          />
        </div>
      </div>
    </>
  );
}
