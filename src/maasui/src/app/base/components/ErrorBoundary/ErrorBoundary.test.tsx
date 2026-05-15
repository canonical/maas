import * as Sentry from "@sentry/browser";

import ErrorBoundary, { Labels } from "./ErrorBoundary";

import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("ErrorBoundary", () => {
  let state: RootState;

  afterEach(() => {
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    state = factory.rootState({
      general: factory.generalState({
        version: factory.versionState({ data: "2.7.0" }),
      }),
    });
  });

  it("should display an ErrorMessage if wrapped component throws", () => {
    vi.spyOn(console, "error").mockImplementation(() => null); // suppress traceback in test

    const Component = () => {
      throw new Error("kerblam");
    };
    renderWithProviders(
      <ErrorBoundary>
        <Component />
      </ErrorBoundary>,
      { state }
    );

    expect(screen.getByText(Labels.ErrorMessage)).toBeInTheDocument();
  });

  it("should not capture exceptions with Sentry when enable_analytics is disabled", () => {
    vi.spyOn(console, "error").mockImplementation(() => null); // suppress traceback in test
    vi.spyOn(Sentry, "captureException").mockImplementation(() => "");

    state.config.items = [
      {
        name: ConfigNames.ENABLE_ANALYTICS,
        value: false,
      },
    ];

    const Component = () => {
      throw new Error("kerblam");
    };
    renderWithProviders(
      <ErrorBoundary>
        <Component />
      </ErrorBoundary>,
      { state }
    );

    expect(Sentry.captureException).toHaveBeenCalledTimes(0);
  });

  it("should capture exceptions with Sentry when enable_analytics is enabled", () => {
    vi.spyOn(console, "error").mockImplementation(() => null); // suppress traceback in test
    vi.spyOn(Sentry, "captureException").mockImplementation(() => "");

    state.config.items = [
      {
        name: ConfigNames.ENABLE_ANALYTICS,
        value: true,
      },
    ];

    const Component = () => {
      throw new Error("kerblam");
    };
    renderWithProviders(
      <ErrorBoundary>
        <Component />
      </ErrorBoundary>,
      { state }
    );

    expect(Sentry.captureException).toHaveBeenCalledTimes(1);
  });
});
