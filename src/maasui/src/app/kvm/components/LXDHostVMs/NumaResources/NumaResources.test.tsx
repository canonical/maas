import NumaResources, { TRUNCATION_POINT } from "./NumaResources";

import * as hooks from "@/app/base/hooks/analytics";
import { ConfigNames } from "@/app/store/config/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("NumaResources", () => {
  it("can expand truncated NUMA nodes if above truncation point", async () => {
    const pod = factory.pod({
      id: 1,
      resources: factory.podResources({
        numa: Array.from(Array(TRUNCATION_POINT + 1)).map(() =>
          factory.podNuma()
        ),
      }),
    });
    const state = factory.rootState({
      pod: factory.podState({ items: [pod] }),
    });

    renderWithProviders(<NumaResources id={pod.id} />, {
      state,
    });

    expect(screen.getByTestId("show-more-numas")).toBeInTheDocument();
    expect(screen.getAllByLabelText("numa resources card")).toHaveLength(
      TRUNCATION_POINT
    );

    await userEvent.click(screen.getByTestId("show-more-numas"));

    expect(screen.getByTestId("show-more-numas")).toHaveTextContent(
      "Show less NUMA nodes"
    );
    expect(screen.getAllByLabelText("numa resources card")).toHaveLength(
      TRUNCATION_POINT + 1
    );
  });

  it("shows wide cards if the pod has less than or equal to 2 NUMA nodes", () => {
    const pod = factory.pod({
      id: 1,
      resources: factory.podResources({
        numa: [factory.podNuma()],
      }),
    });
    const state = factory.rootState({
      pod: factory.podState({ items: [pod] }),
    });
    renderWithProviders(<NumaResources id={pod.id} />, {
      state,
    });

    expect(screen.getByTestId("numa-resources")).toHaveClass("is-wide");
  });

  it("can send an analytics event when expanding NUMA nodes if analytics enabled", async () => {
    const pod = factory.pod({
      id: 1,
      resources: factory.podResources({
        numa: Array.from(Array(TRUNCATION_POINT + 1)).map(() =>
          factory.podNuma()
        ),
      }),
    });
    const state = factory.rootState({
      config: factory.configState({
        items: [
          factory.config({
            name: ConfigNames.ENABLE_ANALYTICS,
            value: false,
          }),
        ],
      }),
      pod: factory.podState({ items: [pod] }),
    });
    const useSendMock = vi.spyOn(hooks, "useSendAnalytics");
    renderWithProviders(<NumaResources id={pod.id} />, {
      state,
    });

    await userEvent.click(screen.getByTestId("show-more-numas"));
    expect(useSendMock).toHaveBeenCalled();
    useSendMock.mockRestore();
  });
});
