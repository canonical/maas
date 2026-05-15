import { useFetchActions } from "./dataFetching";

import { renderHookWithMockStore } from "@/testing/utils";

const mockDispatch = vi.fn();
const mockAction = vi.fn(() => ({
  type: "MOCK_ACTION",
}));

vi.mock("react-redux", async () => {
  const actual: object = await vi.importActual("react-redux");
  return { ...actual, useDispatch: () => mockDispatch, useSelector: () => 0 };
});

afterEach(() => {
  vi.clearAllMocks();
});

it("runs the actions once on mount and doesn't run again on rerender", async () => {
  const { rerender } = await renderHookWithMockStore(() => {
    useFetchActions([mockAction]);
  });

  expect(mockDispatch).toHaveBeenCalledTimes(1);
  expect(mockAction).toHaveBeenCalledTimes(1);

  mockAction.mockClear();
  mockDispatch.mockClear();

  rerender();

  expect(mockDispatch).not.toHaveBeenCalled();
  expect(mockAction).not.toHaveBeenCalled();
});
