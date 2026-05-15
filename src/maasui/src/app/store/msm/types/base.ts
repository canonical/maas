export interface MsmStatus {
  smUrl: string | null;
  running: "connected" | "not_connected" | "pending";
  startTime: string | null;
}

export interface MsmState {
  status: MsmStatus | null;
  loading: boolean;
  loaded: boolean;
  errors: string | null;
}
