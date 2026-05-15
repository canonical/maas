import { Labels as ScriptsListLabels } from "./ScriptsList";

import ScriptsList from ".";

import { fileContextStore } from "@/app/base/file-context";
import type { RootState } from "@/app/store/root/types";
import { ScriptType } from "@/app/store/script/types";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  within,
} from "@/testing/utils";

describe("ScriptsList", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  afterAll(() => {
    vi.restoreAllMocks();
  });

  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      script: factory.scriptState({
        loaded: true,
        items: [
          factory.script({
            id: 1,
            name: "commissioning-script",
            description: "a commissioning script",
            script_type: ScriptType.COMMISSIONING,
          }),
          factory.script({
            id: 2,
            name: "testing-script",
            description: "a testing script",
            script_type: ScriptType.TESTING,
          }),
          factory.script({
            id: 3,
            name: "testing-script-2",
            description: "another testing script",
            script_type: ScriptType.TESTING,
          }),
          factory.script({
            id: 4,
            name: "deployment-script",
            description: "a deployment script",
            script_type: ScriptType.DEPLOYMENT,
          }),
        ],
      }),
    });
  });

  it("fetches scripts if they haven't been loaded yet", () => {
    state.script.loaded = false;
    const { store } = renderWithProviders(<ScriptsList />, { state });
    expect(
      store.getActions().some((action) => action.type === "script/fetch")
    ).toBe(true);
  });

  it("does not fetch scripts if they've already been loaded", () => {
    state.script.loaded = true;
    const { store } = renderWithProviders(<ScriptsList />, { state });

    expect(
      store.getActions().some((action) => action.type === "script/fetch")
    ).toBe(false);
  });

  it("Displays commissioning scripts by default", () => {
    renderWithProviders(<ScriptsList />, { state });

    expect(screen.getAllByTestId("script-row")).toHaveLength(1);

    const commissioning_script = screen.getByRole("row", {
      name: "commissioning-script",
    });

    expect(commissioning_script).toBeInTheDocument();
    expect(
      within(commissioning_script).getByRole("gridcell", {
        name: "a commissioning script",
      })
    ).toBeInTheDocument();
  });

  it("Displays testing scripts", () => {
    renderWithProviders(<ScriptsList type="testing" />, { state });

    expect(screen.getAllByTestId("script-row")).toHaveLength(2);

    const testing_script = screen.getByRole("row", {
      name: "testing-script",
    });

    const another_testing_script = screen.getByRole("row", {
      name: "testing-script-2",
    });

    expect(testing_script).toBeInTheDocument();
    expect(
      within(testing_script).getByRole("gridcell", {
        name: "a testing script",
      })
    ).toBeInTheDocument();

    expect(another_testing_script).toBeInTheDocument();
    expect(
      within(another_testing_script).getByRole("gridcell", {
        name: "another testing script",
      })
    ).toBeInTheDocument();
  });

  it("Displays deployment scripts", () => {
    renderWithProviders(<ScriptsList type="deployment" />, { state });

    expect(screen.getAllByTestId("script-row")).toHaveLength(1);

    const deployment_script = screen.getByRole("row", {
      name: "deployment-script",
    });

    expect(deployment_script).toBeInTheDocument();
    expect(
      within(deployment_script).getByRole("gridcell", {
        name: "a deployment script",
      })
    ).toBeInTheDocument();
  });

  it("can show a delete confirmation", async () => {
    renderWithProviders(<ScriptsList />, { state });

    let row = screen.getByRole("row", { name: "commissioning-script" });
    expect(row).not.toHaveClass("is-active");
    // Click on the delete button:
    await userEvent.click(
      within(within(row).getByLabelText(ScriptsListLabels.Actions)).getByRole(
        "button",
        { name: "Delete" }
      )
    );
    row = screen.getByRole("row", { name: "commissioning-script" });
    expect(row).toHaveClass("is-active");
  });

  it("disables the delete button if a default script", () => {
    const state = factory.rootState({
      script: factory.scriptState({
        loaded: true,
        items: [
          factory.script({
            default: true,
            script_type: ScriptType.TESTING,
          }),
          factory.script({
            default: false,
            script_type: ScriptType.TESTING,
          }),
        ],
      }),
    });

    renderWithProviders(<ScriptsList type="testing" />, { state });

    expect(
      within(
        within(screen.getByRole("row", { name: "test name 29" })).getByRole(
          "gridcell",
          { name: ScriptsListLabels.Actions }
        )
      ).getByRole("button")
    ).toBeAriaDisabled();

    expect(
      within(
        within(screen.getByRole("row", { name: "test name 30" })).getByRole(
          "gridcell",
          { name: ScriptsListLabels.Actions }
        )
      ).getByRole("button")
    ).not.toBeAriaDisabled();
  });

  it("can delete a script", async () => {
    const { store } = renderWithProviders(<ScriptsList />, { state });
    const row = screen.getByRole("row", { name: "commissioning-script" });
    expect(row).not.toHaveClass("is-active");
    // Click on the delete button:
    await userEvent.click(
      within(within(row).getByLabelText(ScriptsListLabels.Actions)).getByRole(
        "button",
        { name: "Delete" }
      )
    );
    // Click on the delete confirm button
    await userEvent.click(
      within(
        within(row).getByLabelText(ScriptsListLabels.DeleteConfirm)
      ).getByRole("button", { name: "Delete" })
    );

    expect(
      store.getActions().find((action) => action.type === "script/delete")
    ).toEqual({
      meta: {
        method: "delete",
        model: "script",
      },
      type: "script/delete",
      payload: {
        params: {
          id: 1,
        },
      },
    });
  });

  it("can show script source", async () => {
    vi.spyOn(fileContextStore, "get").mockReturnValue("test script contents");

    renderWithProviders(<ScriptsList />, { state });
    let row = screen.getByRole("row", { name: "commissioning-script" });
    expect(row).not.toHaveClass("is-active");

    // Click on the expand button:
    await userEvent.click(
      within(row).getByRole("button", { name: "Show/hide details" })
    );
    row = screen.getByRole("row", { name: "commissioning-script" });
    expect(row).toHaveClass("is-active");

    // expect script source to be decoded base64
    expect(screen.getByText("test script contents")).toBeInTheDocument();
  });

  it("displays a message if there are no scripts", () => {
    const state = factory.rootState({
      script: factory.scriptState({
        loaded: true,
        items: [],
      }),
    });

    renderWithProviders(<ScriptsList type="testing" />, { state });

    expect(screen.getByText(ScriptsListLabels.EmptyList)).toBeInTheDocument();
  });
});
