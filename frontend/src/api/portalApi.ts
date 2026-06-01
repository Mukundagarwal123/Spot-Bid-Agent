import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  CarrierCRMResponse,
  LaneCreateRequest,
  LaneCreatedResponse,
  LaneDetailResponse,
  LanesListResponse,
} from "../types/portal";

const api = axios.create({ baseURL: "/" });

// ---------------------------------------------------------------------------
// Raw fetch functions
// ---------------------------------------------------------------------------

export async function fetchLanes(): Promise<LanesListResponse> {
  const { data } = await api.get<LanesListResponse>("/portal/lanes");
  return data;
}

export async function fetchLaneDetail(laneId: string): Promise<LaneDetailResponse> {
  const { data } = await api.get<LaneDetailResponse>(`/portal/lanes/${laneId}`);
  return data;
}

export async function fetchCarrierCRM(laneId: string): Promise<CarrierCRMResponse> {
  const { data } = await api.get<CarrierCRMResponse>(
    `/portal/lanes/${laneId}/carrier-crm`
  );
  return data;
}

export async function createLane(
  req: LaneCreateRequest
): Promise<LaneCreatedResponse> {
  const { data } = await api.post<LaneCreatedResponse>("/portal/lanes", req);
  return data;
}

// ---------------------------------------------------------------------------
// React Query hooks
// ---------------------------------------------------------------------------

export function useLanes() {
  return useQuery({
    queryKey: ["lanes"],
    queryFn: fetchLanes,
    staleTime: 10_000,
  });
}

export function useLaneDetail(laneId: string | null) {
  return useQuery({
    queryKey: ["lane", laneId],
    queryFn: () => fetchLaneDetail(laneId!),
    enabled: laneId !== null,
    staleTime: 30_000,
  });
}

export function useCarrierCRM(laneId: string | null) {
  return useQuery({
    queryKey: ["carrier-crm", laneId],
    queryFn: () => fetchCarrierCRM(laneId!),
    enabled: laneId !== null,
    staleTime: 30_000,
  });
}

export function useCreateLane() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createLane,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["lanes"] });
    },
  });
}
