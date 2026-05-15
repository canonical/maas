import ScriptDetails from ".";

import FileContext, { fileContextStore } from "@/app/base/file-context";
import type { RootState } from "@/app/store/root/types";
import { ScriptType } from "@/app/store/script/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("ScriptDetails", () => {
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
        ],
      }),
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  afterAll(() => {
    vi.restoreAllMocks();
  });

  it("fetches the script", () => {
    const { store } = renderWithProviders(<ScriptDetails id={1} />, { state });
    expect(
      store.getActions().some((action) => action.type === "script/get")
    ).toBe(true);
  });

  it("displays a spinner while loading", () => {
    state.script.loading = true;
    renderWithProviders(<ScriptDetails id={1} />, { state });
    expect(screen.getByText("Loading")).toBeInTheDocument();
  });

  it("displays a message when the script does not exist", () => {
    renderWithProviders(<ScriptDetails id={1} />, { state });
    expect(screen.getByText("Script could not be found")).toBeInTheDocument();
  });

  it("can display the script", () => {
    vi.spyOn(fileContextStore, "get").mockReturnValue("test script contents");
    renderWithProviders(
      <FileContext.Provider value={fileContextStore}>
        <ScriptDetails id={1} />
      </FileContext.Provider>,
      { state }
    );

    expect(screen.getByText("test script contents")).toBeInTheDocument();
  });

  it("displays a collapse button if 'isCollapsible' prop is provided", () => {
    vi.spyOn(fileContextStore, "get").mockReturnValue("some random text");
    renderWithProviders(
      <FileContext.Provider value={fileContextStore}>
        <ScriptDetails id={1} isCollapsible />
      </FileContext.Provider>,
      { state }
    );

    expect(
      screen.getByRole("button", { name: /close snippet/i })
    ).toBeInTheDocument();
  });

  it("doesn't display a collapse button if 'isCollapsible' prop is not provided", () => {
    vi.spyOn(fileContextStore, "get").mockReturnValue("some random text");
    renderWithProviders(
      <FileContext.Provider value={fileContextStore}>
        <ScriptDetails id={1} />
      </FileContext.Provider>,
      { state }
    );

    expect(
      screen.queryByRole("button", { name: /close snippet/i })
    ).not.toBeInTheDocument();
  });
});
