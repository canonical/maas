import * as reactQuery from "@tanstack/react-query";
import type { UseQueryOptions } from "@tanstack/react-query";
import { waitFor } from "@testing-library/react";

import { useWebsocketAwareQuery } from "./base";

import { rootState, statusState } from "@/testing/factories";
import { renderHookWithMockStore } from "@/testing/utils";

vi.mock("@tanstack/react-query");

const mockOptions = {} as UseQueryOptions;

beforeEach(() => {
  vi.resetAllMocks();
  const mockQueryClient: Partial<reactQuery.QueryClient> = {};
  vi.mocked(reactQuery.useQueryClient).mockReturnValue(
    mockQueryClient as reactQuery.QueryClient
  );
  vi.mocked(reactQuery.useQuery).mockReturnValue({
    data: "testData",
    isLoading: false,
  } as reactQuery.UseQueryResult);
});

it("calls useQuery with correct parameters", () => {
  renderHookWithMockStore(() => useWebsocketAwareQuery(mockOptions));
  expect(reactQuery.useQuery).toHaveBeenCalledWith(mockOptions);
});

it("skips query invalidation when connectedCount is unchanged", () => {
  const initialState = rootState({
    status: statusState({ connectedCount: 0 }),
  });
  const { rerender } = renderHookWithMockStore(
    () => useWebsocketAwareQuery(mockOptions),
    { initialState }
  );

  const mockInvalidateQueries = vi.fn();
  const mockQueryClient: Partial<reactQuery.QueryClient> = {
    invalidateQueries: mockInvalidateQueries,
  };
  vi.mocked(reactQuery.useQueryClient).mockReturnValue(
    mockQueryClient as reactQuery.QueryClient
  );

  rerender(() => useWebsocketAwareQuery(mockOptions), {
    state: rootState({
      status: statusState({ connectedCount: 0 }),
    }),
  });
  expect(mockInvalidateQueries).not.toHaveBeenCalled();
});

it("invalidates queries when connectedCount changes", async () => {
  const initialState = rootState({
    status: statusState({ connectedCount: 0 }),
  });
  const { rerender } = renderHookWithMockStore(
    () => useWebsocketAwareQuery(mockOptions),
    { initialState }
  );

  const mockInvalidateQueries = vi.fn();
  const mockQueryClient: Partial<reactQuery.QueryClient> = {
    invalidateQueries: mockInvalidateQueries,
  };
  vi.mocked(reactQuery.useQueryClient).mockReturnValue(
    mockQueryClient as reactQuery.QueryClient
  );

  rerender(() => useWebsocketAwareQuery(mockOptions), {
    state: rootState({
      status: statusState({ connectedCount: 1 }),
    }),
  });
  await waitFor(() => {
    expect(mockInvalidateQueries).toHaveBeenCalled();
  });
});

it("returns the result of useQuery", () => {
  const { result } = renderHookWithMockStore(() =>
    useWebsocketAwareQuery(mockOptions)
  );
  expect(result.current).not.toBeNull();
  expect(result.current).toEqual({ data: "testData", isLoading: false });
});
