export type EquipmentType =
  | "dry_van"
  | "reefer"
  | "flatbed"
  | "power_only"
  | "other";

export const EQUIPMENT_LABELS: Record<EquipmentType, string> = {
  dry_van: "Dry Van",
  reefer: "Reefer",
  flatbed: "Flatbed",
  power_only: "Power Only",
  other: "Other",
};

export interface StopInput {
  city: string;
  state: string;
  zip?: string;
}

export interface LaneCreateRequest {
  origin_city: string;
  origin_state: string;
  origin_zip?: string;
  destination_city: string;
  destination_state: string;
  destination_zip?: string;
  stops: StopInput[];
  equipment_type: EquipmentType;
  pickup_date?: string;
}

export interface LaneCreatedResponse {
  lane_id: string;
  label: string;
  status: string;
  created_at: string;
}

export interface MetricsPreview {
  carriers_contacted: number;
  carriers_responded: number;
}

export interface LaneSummary {
  lane_id: string;
  label: string;
  equipment_type: EquipmentType;
  status: string;
  last_activity_at: string;
  pickup_date: string | null;
  metrics_preview: MetricsPreview;
}

export interface LanesListResponse {
  lanes: LaneSummary[];
}

export interface StopInfo {
  stop_order: number;
  city: string;
  state: string;
  zip: string | null;
}

export interface LaneInfo {
  lane_id: string;
  label: string;
  origin_city: string;
  origin_state: string;
  origin_zip: string | null;
  destination_city: string;
  destination_state: string;
  destination_zip: string | null;
  equipment_type: EquipmentType;
  pickup_date: string | null;
  status: string;
  created_at: string;
}

export interface MetricsSnapshot {
  emails_sent: number;
  emails_clicked: number;
  email_replies: number;
  sms_sent: number;
  sms_replies: number;
  whatsapp_sent: number;
  whatsapp_replies: number;
  carriers_contacted: number;
  carriers_responded: number;
}

export interface TimelineEvent {
  event_type: string;
  label: string;
  timestamp: string;
  channel: string | null;
}

export interface LaneDetailResponse {
  lane: LaneInfo;
  stops: StopInfo[];
  metrics: MetricsSnapshot;
  timeline: TimelineEvent[];
}

export interface CarrierCRMItem {
  carrier_name: string;
  times_contacted: number;
  times_responded: number;
  avg_response_time_minutes: number;
  preferred_channel: string;
  response_rate: number;
  last_contacted_at: string;
}

export interface CarrierCRMResponse {
  carriers: CarrierCRMItem[];
}
