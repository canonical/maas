import KernelParametersForm, {
  Labels as FormLabels,
} from "./KernelParametersForm";

import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  screen,
  renderWithProviders,
  userEvent,
  waitFor,
} from "@/testing/utils";

describe("KernelParametersForm", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        items: [
          {
            name: ConfigNames.KERNEL_OPTS,
            value: "foo",
          },
          {
            name: ConfigNames.ENABLE_KERNEL_CRASH_DUMP,
            value: false,
          },
        ],
      }),
    });
  });

  it("sets kernel_opts value", () => {
    renderWithProviders(<KernelParametersForm />, { state });
    expect(
      screen.getByRole("textbox", {
        name: FormLabels.GlobalBootParams,
      })
    ).toHaveValue("foo");
  });

  it("sets enable_kernel_crash_dump value", () => {
    state.config.items = [
      { name: ConfigNames.ENABLE_KERNEL_CRASH_DUMP, value: true },
    ];

    renderWithProviders(<KernelParametersForm />, { state });

    expect(
      screen.getByRole("checkbox", { name: FormLabels.KernelCrashDump })
    ).toBeChecked();
  });

  it("dispatches an action to update kernel parameters", async () => {
    const { store } = renderWithProviders(<KernelParametersForm />, { state });

    await userEvent.clear(
      screen.getByRole("textbox", { name: FormLabels.GlobalBootParams })
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: FormLabels.GlobalBootParams }),
      "bar"
    );

    await userEvent.click(
      screen.getByRole("checkbox", { name: FormLabels.KernelCrashDump })
    );

    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(
      store.getActions().find((action) => action.type === "config/update")
    ).toStrictEqual({
      meta: {
        method: "bulk_update",
        model: "config",
      },
      type: "config/update",
      payload: {
        params: {
          items: {
            enable_kernel_crash_dump: true,
            kernel_opts: "bar",
          },
        },
      },
    });
  });

  it("shows a tooltip for minimum OS requirements", async () => {
    renderWithProviders(<KernelParametersForm />, {
      state,
    });

    await userEvent.hover(
      screen.getAllByRole("button", { name: "help-mid-dark" })[1]
    );

    await waitFor(() => {
      expect(screen.getByRole("tooltip")).toHaveTextContent(
        "Tested with Ubuntu 24.04 LTS or higher."
      );
    });
  });

  it("shows a tooltip for minimum hardware requirements", async () => {
    renderWithProviders(<KernelParametersForm />, {
      state,
    });

    await userEvent.hover(
      screen.getAllByRole("button", { name: "help-mid-dark" })[0]
    );

    await waitFor(() => {
      expect(screen.getByRole("tooltip")).toHaveTextContent(
        ">= 4 CPU threads, >= 6GB RAM, Reserve >5x RAM size as free disk space in /var."
      );
    });
  });
});
