import AuthenticationCard from "./AuthenticationCard";

import { PodType } from "@/app/store/pod/constants";
import type { PodDetails, PodPowerParameters } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("AuthenticationCard", () => {
  let state: RootState;
  let pod: PodDetails;

  beforeEach(() => {
    pod = factory.podDetails({
      certificate: factory.certificateMetadata(),
      id: 1,
      power_parameters: factory.podPowerParameters({
        certificate: "abc123",
        key: "abc123",
      }),
      type: PodType.LXD,
    });
    state = factory.rootState({
      pod: factory.podState({ items: [pod] }),
    });
  });

  it("shows a spinner if pod is not PodDetails type", () => {
    state.pod.items[0] = factory.pod({ id: 1 });
    renderWithProviders(<AuthenticationCard hostId={pod.id} />, {
      state,
    });
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("can open the update certificate form", async () => {
    renderWithProviders(<AuthenticationCard hostId={pod.id} />, {
      state,
    });
    expect(screen.queryByText("Update Certificate")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("form", { name: "Update certificate" })
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByTestId("show-update-certificate"));

    expect(
      screen.getByRole("form", { name: "Update certificate" })
    ).toBeInTheDocument();
  });

  it("opens the update certificate form automatically if pod has no certificate", () => {
    pod.certificate = undefined;
    const power_parameters = pod.power_parameters as PodPowerParameters;
    power_parameters.certificate = undefined;
    power_parameters.key = undefined;
    renderWithProviders(<AuthenticationCard hostId={pod.id} />, {
      state,
    });

    expect(
      screen.getByRole("form", { name: "Update certificate" })
    ).toBeInTheDocument();
  });
});
