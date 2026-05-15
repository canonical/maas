import { useMachineActionMenus } from "./hooks";

import { NodeActions } from "@/app/store/types/node";
import { renderHookWithProviders } from "@/testing/utils";

describe("useMachineActionMenus", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  // TODO: Remove when DPU feature flag is removed https://warthogs.atlassian.net/browse/MAASENG-4186
  it("includes 'Power cycle' when the DPU feature flag is enabled", () => {
    vi.stubEnv("VITE_APP_DPU_PROVISIONING", "true");
    const { result } = renderHookWithProviders(() =>
      useMachineActionMenus(false)
    );

    expect(
      result.current
        .find((group) => group.name === "power")
        ?.items.some((item) => item.action === NodeActions.POWER_CYCLE)
    ).toBe(true);
  });

  // TODO: Remove when DPU feature flag is removed https://warthogs.atlassian.net/browse/MAASENG-4186
  it("excludes 'Power cycle' when the DPU feature flag is disabled", () => {
    vi.stubEnv("VITE_APP_DPU_PROVISIONING", "false");
    const { result } = renderHookWithProviders(() =>
      useMachineActionMenus(false)
    );

    expect(
      result.current
        .find((group) => group.name === "power")
        ?.items.some((item) => item.action === NodeActions.POWER_CYCLE)
    ).toBe(false);
  });

  it("includes 'Check power' if viewing details and a system ID is provided", () => {
    const { result } = renderHookWithProviders(() =>
      useMachineActionMenus(true, "abc123")
    );

    expect(
      result.current
        .find((group) => group.name === "power")
        ?.items.some((item) => item.action === NodeActions.CHECK_POWER)
    ).toBe(true);
  });

  it("excludes 'Check power' if viewing details and a system ID is not provided", () => {
    const { result } = renderHookWithProviders(() =>
      useMachineActionMenus(true, undefined)
    );

    expect(
      result.current
        .find((group) => group.name === "power")
        ?.items.some((item) => item.action === NodeActions.CHECK_POWER)
    ).toBe(false);
  });

  it("excludes 'Check power' if not viewing details", () => {
    const { result } = renderHookWithProviders(() =>
      useMachineActionMenus(false)
    );

    expect(
      result.current
        .find((group) => group.name === "power")
        ?.items.some((item) => item.action === NodeActions.CHECK_POWER)
    ).toBe(false);
  });
});
