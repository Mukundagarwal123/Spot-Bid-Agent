import { EQUIPMENT_LABELS } from "../../types/portal";
import type { EquipmentType } from "../../types/portal";

interface Props {
  value: EquipmentType | "";
  error?: string;
  onChange: (value: EquipmentType | "") => void;
  onBlur: () => void;
}

export default function EquipmentSelect({ value, error, onChange, onBlur }: Props) {
  return (
    <div className="form-field">
      <label htmlFor="equipment_type">Equipment Type *</label>
      <select
        id="equipment_type"
        value={value}
        className={error ? "error" : ""}
        onChange={(e) => onChange(e.target.value as EquipmentType | "")}
        onBlur={onBlur}
      >
        <option value="">Select type...</option>
        {(Object.entries(EQUIPMENT_LABELS) as [EquipmentType, string][]).map(
          ([val, label]) => (
            <option key={val} value={val}>
              {label}
            </option>
          )
        )}
      </select>
      {error && <span className="field-error">{error}</span>}
    </div>
  );
}
