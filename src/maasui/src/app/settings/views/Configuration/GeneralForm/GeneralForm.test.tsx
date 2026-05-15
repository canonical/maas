import GeneralForm from "./GeneralForm";

import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

describe("GeneralForm", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        items: [
          factory.config({ name: ConfigNames.MAAS_NAME, value: "bionic-maas" }),
          factory.config({ name: ConfigNames.THEME, value: "default" }),
          factory.config({ name: ConfigNames.ENABLE_ANALYTICS, value: true }),
          factory.config({
            name: ConfigNames.RELEASE_NOTIFICATIONS,
            value: true,
          }),
        ],
      }),
    });
  });

  it("can render", () => {
    renderWithProviders(<GeneralForm />, { state });

    expect(
      screen.getByRole("form", { name: "Configuration - General" })
    ).toBeInTheDocument();
  });

  it("sets maas_name value", () => {
    renderWithProviders(<GeneralForm />, { state });

    expect(screen.getByRole("textbox", { name: "MAAS name" })).toHaveValue(
      "bionic-maas"
    );
  });

  it("sets theme value", () => {
    renderWithProviders(<GeneralForm />, { state });

    expect(
      screen.getByRole("radio", {
        name: "Default",
      })
    ).toHaveProperty("checked", true);
  });

  it("sets enable_analytics value", () => {
    renderWithProviders(<GeneralForm />, { state });

    expect(
      screen.getByRole("checkbox", {
        name: "Enable analytics to shape improvements to user experience",
      })
    ).toHaveProperty("checked", true);
  });

  it("sets release_notifications value", () => {
    renderWithProviders(<GeneralForm />, { state });

    expect(
      screen.getByRole("checkbox", {
        name: "Enable new release notifications",
      })
    ).toHaveProperty("checked", true);
  });

  it("can change the MAAS theme colour", async () => {
    renderWithProviders(<GeneralForm />, { state });

    const redRadioButton = screen.getByRole("radio", { name: "Red" });
    const saveButton = screen.getByRole("button", { name: "Save" });

    await userEvent.click(redRadioButton);
    await userEvent.click(saveButton);

    expect(redRadioButton).toHaveProperty("checked", true);
  });

  it("can trigger usabilla when the notifications are turned off", async () => {
    window.usabilla_live = vi.fn();
    renderWithProviders(<GeneralForm />, { state });

    const release_notifications_checkbox = screen.getByRole("checkbox", {
      name: "Enable new release notifications",
    });

    const saveButton = screen.getByRole("button", { name: "Save" });

    await userEvent.click(release_notifications_checkbox);
    await userEvent.click(saveButton);

    expect(window.usabilla_live).toHaveBeenCalled();
  });
});
