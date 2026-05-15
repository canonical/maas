import ScriptRunTime from "./ScriptRunTime";

import {
  ScriptResultStatus,
  ScriptResultEstimated,
} from "@/app/store/scriptresult/types";
import * as factory from "@/testing/factories";
import { screen, waitFor, renderWithProviders } from "@/testing/utils";

describe("ScriptRunTime", () => {
  beforeEach(() => {
    vi.useFakeTimers().setSystemTime(
      new Date("Thu Apr 01 2021 05:21:58 GMT+0000").getTime()
    );
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("displays the elapsed time when running and runtime is not known", () => {
    const scriptResult = factory.scriptResult({
      estimated_runtime: ScriptResultEstimated.UNKNOWN,
      status: ScriptResultStatus.RUNNING,
      starttime: 1617254218,
    });
    renderWithProviders(<ScriptRunTime scriptResult={scriptResult} />);
    expect(screen.getByText(/0:05:00/i)).toBeInTheDocument();
  });

  it("displays the elapsed time when running and runtime is known", () => {
    const scriptResult = factory.scriptResult({
      estimated_runtime: "0:10:00",
      status: ScriptResultStatus.RUNNING,
      starttime: 1617254218,
    });
    renderWithProviders(<ScriptRunTime scriptResult={scriptResult} />);
    expect(screen.getByText(/0:05:00 of ~0:10:00/i)).toBeInTheDocument();
  });

  it("displays the elapsed time when the the start time is not known", () => {
    const scriptResult = factory.scriptResult({
      estimated_runtime: "0:10:00",
      status: ScriptResultStatus.RUNNING,
      // Use undefined here so that the factory does not set the start time.
      starttime: undefined,
    });
    renderWithProviders(<ScriptRunTime scriptResult={scriptResult} />);
    expect(screen.getByText(/0:00:00 of ~0:10:00/i)).toBeInTheDocument();
  });

  it("displays the elapsed and estimated times when installing and runtime is not known", () => {
    const scriptResult = factory.scriptResult({
      estimated_runtime: ScriptResultEstimated.UNKNOWN,
      status: ScriptResultStatus.INSTALLING,
      starttime: 1617254218,
    });
    renderWithProviders(<ScriptRunTime scriptResult={scriptResult} />);
    expect(screen.getByText(/0:05:00/i)).toBeInTheDocument();
  });

  it("displays the elapsed and estimated times when installing and runtime is known", () => {
    const scriptResult = factory.scriptResult({
      estimated_runtime: "0:10:00",
      status: ScriptResultStatus.INSTALLING,
      starttime: 1617254218,
    });
    renderWithProviders(<ScriptRunTime scriptResult={scriptResult} />);
    expect(screen.getByText(/0:05:00 of ~0:10:00/i)).toBeInTheDocument();
  });

  it("updates the elapsed time every second", async () => {
    const scriptResult = factory.scriptResult({
      estimated_runtime: ScriptResultEstimated.UNKNOWN,
      status: ScriptResultStatus.RUNNING,
      starttime: 1617254218,
    });
    renderWithProviders(<ScriptRunTime scriptResult={scriptResult} />);
    expect(screen.getByText(/0:05:00/i)).toBeInTheDocument();
    vi.advanceTimersByTime(1000);
    await waitFor(() => {
      expect(screen.getByText(/0:05:01/i)).toBeInTheDocument();
    });
  });

  it("only shows the time if less than a day has elapsed", () => {
    const scriptResult = factory.scriptResult({
      estimated_runtime: ScriptResultEstimated.UNKNOWN,
      status: ScriptResultStatus.RUNNING,
      starttime: 1617254218,
    });
    renderWithProviders(<ScriptRunTime scriptResult={scriptResult} />);
    expect(screen.getByText(/0:05:00/i)).toBeInTheDocument();
  });

  it("shows the day and time if one day has elapsed", () => {
    const scriptResult = factory.scriptResult({
      estimated_runtime: ScriptResultEstimated.UNKNOWN,
      status: ScriptResultStatus.RUNNING,
      starttime: 1617167818,
    });
    renderWithProviders(<ScriptRunTime scriptResult={scriptResult} />);
    expect(screen.getByText(/1 day, 0:05:00/i)).toBeInTheDocument();
  });

  it("shows the days and time if more than one day has elapsed", () => {
    const scriptResult = factory.scriptResult({
      estimated_runtime: ScriptResultEstimated.UNKNOWN,
      status: ScriptResultStatus.RUNNING,
      starttime: 1617081418,
    });
    renderWithProviders(<ScriptRunTime scriptResult={scriptResult} />);
    expect(screen.getByText(/2 days, 0:05:00/i)).toBeInTheDocument();
  });

  it("displays the estimated time when pending and runtime is known", () => {
    const scriptResult = factory.scriptResult({
      estimated_runtime: "0:10:00",
      status: ScriptResultStatus.PENDING,
    });
    renderWithProviders(<ScriptRunTime scriptResult={scriptResult} />);
    expect(screen.getByText(/~0:10:00/i)).toBeInTheDocument();
  });

  it("displays the runtime for other statuses", () => {
    const scriptResult = factory.scriptResult({
      runtime: "0:15:00",
      status: ScriptResultStatus.FAILED_APPLYING_NETCONF,
    });
    renderWithProviders(<ScriptRunTime scriptResult={scriptResult} />);
    expect(screen.getByText(/0:15:00/i)).toBeInTheDocument();
  });
});
