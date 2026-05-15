import type { ToastNotificationType } from "@canonical/react-components";

import {
  convertBackendIdToToastNotificationId,
  convertToastNotificationIdToBackendId,
  useDismissNotification,
  useDismissNotifications,
  useListNotifications,
  useNotifications,
} from "./notifications";

import {
  mockNotifications,
  notificationResolvers,
} from "@/testing/resolvers/notifications";
import {
  renderHookWithProviders,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

const successMock = vi.fn();
const failureMock = vi.fn();
const cautionMock = vi.fn();
const infoMock = vi.fn();

vi.mock("@canonical/react-components", async (orig) => {
  const actual = (await orig()) as Record<string, unknown>;
  return {
    ...actual,
    useToastNotification: () => ({
      success: successMock,
      failure: failureMock,
      caution: cautionMock,
      info: infoMock,
    }),
  };
});

setupMockServer(
  notificationResolvers.listNotifications.handler(),
  notificationResolvers.dismissNotification.handler()
);

describe("useListNotifications", () => {
  it("should return notifications data", async () => {
    const { result } = renderHookWithProviders(() => useListNotifications());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toMatchObject(mockNotifications);
  });
});

describe("useDismissNotification", () => {
  it("should dismiss a notification", async () => {
    const { result } = renderHookWithProviders(() => useDismissNotification());
    result.current.mutate({ path: { notification_id: 1 } });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("ID conversion helpers", () => {
  it("should convert backend id to toast id", () => {
    expect(convertBackendIdToToastNotificationId(42)).toBe("notification-42");
  });

  it("should convert toast id back to backend id", () => {
    expect(convertToastNotificationIdToBackendId("notification-42")).toBe(42);
  });
});

describe("useNotifications", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should show success notification", async () => {
    renderHookWithProviders(() => {
      useNotifications();
    });

    await waitFor(() => {
      expect(successMock).toHaveBeenCalled();
    });
  });
});

describe("useDismissNotifications", () => {
  it("should dismiss notification with correct id", async () => {
    const mutateMock = vi.fn();
    const { result } = renderHookWithProviders(() =>
      useDismissNotifications(mutateMock)
    );
    result.current([
      { id: "notification-1" } as ToastNotificationType,
      { id: "notification-2" } as ToastNotificationType,
    ]);
    await waitFor(() => {
      expect(mutateMock).toHaveBeenCalledTimes(2);
    });
    expect(mutateMock).toHaveBeenCalledWith({
      path: { notification_id: 1 },
    });
    expect(mutateMock).toHaveBeenCalledWith({
      path: { notification_id: 2 },
    });
  });
});
