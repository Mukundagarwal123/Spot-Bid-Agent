import { useState } from "react";
import type { EquipmentType, LaneCreateRequest, StopInput } from "../../types/portal";
import { useCreateLane } from "../../api/portalApi";
import EquipmentSelect from "./EquipmentSelect";
import LocationFields from "./LocationFields";
import StopsRepeater from "./StopsRepeater";

interface FormState {
  origin_city: string;
  origin_state: string;
  origin_zip: string;
  destination_city: string;
  destination_state: string;
  destination_zip: string;
  equipment_type: EquipmentType | "";
  pickup_date: string;
  stops: StopInput[];
}

const EMPTY: FormState = {
  origin_city: "",
  origin_state: "",
  origin_zip: "",
  destination_city: "",
  destination_state: "",
  destination_zip: "",
  equipment_type: "",
  pickup_date: "",
  stops: [],
};

function validateCity(v: string): string | undefined {
  return v.trim().length < 2 ? "At least 2 characters" : undefined;
}

function validateState(v: string): string | undefined {
  return v.trim().length !== 2 ? "2-letter code required" : undefined;
}

interface Props {
  onCreated: (laneId: string) => void;
  onCancel?: () => void;
}

export default function LaneIntakeForm({ onCreated, onCancel }: Props) {
  const [form, setForm] = useState<FormState>(EMPTY);
  const [touched, setTouched] = useState<Set<string>>(new Set());
  const mutation = useCreateLane();

  function setField(field: string, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function touch(field: string) {
    setTouched((t) => new Set(t).add(field));
  }

  function addStop() {
    setForm((f) => ({ ...f, stops: [...f.stops, { city: "", state: "", zip: "" }] }));
  }

  function removeStop(i: number) {
    setForm((f) => ({ ...f, stops: f.stops.filter((_, idx) => idx !== i) }));
  }

  function changeStop(i: number, field: keyof StopInput, value: string) {
    setForm((f) => {
      const stops = [...f.stops];
      stops[i] = { ...stops[i], [field]: value };
      return { ...f, stops };
    });
  }

  const errors = {
    origin_city: touched.has("origin_city") ? validateCity(form.origin_city) : undefined,
    origin_state: touched.has("origin_state") ? validateState(form.origin_state) : undefined,
    destination_city: touched.has("destination_city")
      ? validateCity(form.destination_city)
      : undefined,
    destination_state: touched.has("destination_state")
      ? validateState(form.destination_state)
      : undefined,
    equipment_type:
      touched.has("equipment_type") && !form.equipment_type
        ? "Required"
        : undefined,
  };

  const isValid =
    !validateCity(form.origin_city) &&
    !validateState(form.origin_state) &&
    !validateCity(form.destination_city) &&
    !validateState(form.destination_state) &&
    !!form.equipment_type;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid || !form.equipment_type) return;

    const payload: LaneCreateRequest = {
      origin_city: form.origin_city.trim(),
      origin_state: form.origin_state.toUpperCase(),
      origin_zip: form.origin_zip.trim() || undefined,
      destination_city: form.destination_city.trim(),
      destination_state: form.destination_state.toUpperCase(),
      destination_zip: form.destination_zip.trim() || undefined,
      equipment_type: form.equipment_type,
      pickup_date: form.pickup_date || undefined,
      stops: form.stops
        .filter((s) => s.city.trim())
        .map((s) => ({
          city: s.city.trim(),
          state: s.state.toUpperCase(),
          zip: s.zip?.trim() || undefined,
        })),
    };

    const result = await mutation.mutateAsync(payload);
    setForm(EMPTY);
    setTouched(new Set());
    onCreated(result.lane_id);
  }

  return (
    <form className="lane-form" onSubmit={handleSubmit} noValidate>
      <h2>New Lane</h2>

      <LocationFields
        prefix="origin"
        label="Origin"
        city={form.origin_city}
        state={form.origin_state}
        zip={form.origin_zip}
        cityError={errors.origin_city}
        stateError={errors.origin_state}
        onChange={setField}
        onBlur={touch}
      />

      <LocationFields
        prefix="destination"
        label="Destination"
        city={form.destination_city}
        state={form.destination_state}
        zip={form.destination_zip}
        cityError={errors.destination_city}
        stateError={errors.destination_state}
        onChange={setField}
        onBlur={touch}
      />

      <StopsRepeater
        stops={form.stops}
        onAdd={addStop}
        onRemove={removeStop}
        onChange={changeStop}
      />

      <div className="form-row two-col" style={{ marginTop: 16 }}>
        <EquipmentSelect
          value={form.equipment_type}
          error={errors.equipment_type}
          onChange={(v) => setField("equipment_type", v)}
          onBlur={() => touch("equipment_type")}
        />
        <div className="form-field">
          <label htmlFor="pickup_date">Pickup Date</label>
          <input
            id="pickup_date"
            type="date"
            value={form.pickup_date}
            onChange={(e) => setField("pickup_date", e.target.value)}
          />
        </div>
      </div>

      {mutation.isError && (
        <div className="field-error" style={{ marginTop: 8 }}>
          Failed to create lane. Please try again.
        </div>
      )}

      <div className="form-actions">
        <button
          type="submit"
          className="btn-primary"
          disabled={!isValid || mutation.isPending}
        >
          {mutation.isPending ? "Creating..." : "Create Lane"}
        </button>
        {onCancel && (
          <button type="button" className="btn-secondary" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
