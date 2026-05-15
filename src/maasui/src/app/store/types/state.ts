export type EventError<I, E, K extends keyof I> = {
  id: I[K] | null;
  callId?: string;
  error: E;
  event: string | null;
};

export type GenericState<I, E> = {
  errors: E;
  items: I[];
  loaded: boolean;
  loading: boolean;
  saved: boolean;
  saving: boolean;
};
