import { Labels as RepositoryFormLabels } from "../RepositoryFormFields/RepositoryFormFields";

import EditRepository from "./EditRepository";

import * as repoQueryHooks from "@/app/api/query/packageRepositories";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { packageRepositoriesResolvers } from "@/testing/resolvers/packageRepositories";
import {
  screen,
  within,
  renderWithProviders,
  setupMockServer,
  mockIsPending,
  waitFor,
  waitForLoading,
  userEvent,
  spyOnMutation,
  mockSidePanel,
} from "@/testing/utils";

const { mockClose } = await mockSidePanel();

const mockServer = setupMockServer(
  packageRepositoriesResolvers.getPackageRepository.handler(
    factory.packageRepository({ id: 1, name: "test" })
  ),
  packageRepositoriesResolvers.updatePackageRepository.handler()
);

describe("RepositoryEdit", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      general: factory.generalState({
        componentsToDisable: factory.componentsToDisableState({
          loaded: true,
        }),
        knownArchitectures: factory.knownArchitecturesState({
          loaded: true,
        }),
        pocketsToDisable: factory.pocketsToDisableState({
          loaded: true,
        }),
      }),
    });
  });

  it("runs closeSidePanel function when the cancel button is clicked", async () => {
    renderWithProviders(<EditRepository id={1} type="repository" />, { state });
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: /Cancel/i }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("displays a loading component if loading", () => {
    mockIsPending();
    renderWithProviders(<EditRepository id={1} type={"ppa"} />, { state });
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("dispatches actions to fetch known components, architectures, and pockets on load", () => {
    state.general.componentsToDisable.loaded = false;
    state.general.knownArchitectures.loaded = false;
    state.general.pocketsToDisable.loaded = false;
    const { store } = renderWithProviders(
      <EditRepository id={1} type="ppa" />,
      { state }
    );

    expect(store.getActions()).toEqual([
      {
        type: "general/fetchComponentsToDisable",
        payload: null,
        meta: {
          cache: true,
          model: "general",
          method: "components_to_disable",
        },
      },
      {
        type: "general/fetchKnownArchitectures",
        payload: null,
        meta: { cache: true, model: "general", method: "known_architectures" },
      },
      {
        type: "general/fetchPocketsToDisable",
        payload: null,
        meta: { cache: true, model: "general", method: "pockets_to_disable" },
      },
    ]);
  });

  it("shows an error message if the repository fetch fails", async () => {
    mockServer.use(
      packageRepositoriesResolvers.getPackageRepository.error({
        message: "Uh oh!",
        code: 500,
      })
    );

    renderWithProviders(<EditRepository id={1} type={"ppa"} />, { state });

    await waitFor(() => {
      expect(screen.getByText("Uh oh!")).toBeInTheDocument();
    });
  });

  it("handles 'type' being undefined", async () => {
    renderWithProviders(<EditRepository id={1} type={undefined} />, { state });

    await waitForLoading();

    expect(screen.getByText("Repository not found")).toBeInTheDocument();
  });

  it("shows 'Edit PPA' if type is 'ppa' and a repo is provided", async () => {
    renderWithProviders(<EditRepository id={1} type="ppa" />, { state });

    await waitForLoading();

    expect(screen.getByRole("form", { name: "Edit PPA" })).toBeInTheDocument();
  });

  it("shows 'Edit repository' if type is 'repository' and a repo is provided", async () => {
    renderWithProviders(<EditRepository id={1} type="repository" />, { state });

    await waitForLoading();

    expect(
      screen.getByRole("form", { name: "Edit repository" })
    ).toBeInTheDocument();
  });

  it("can update a repository", async () => {
    renderWithProviders(<EditRepository id={1} type="repository" />, { state });

    await waitForLoading();

    await userEvent.clear(
      screen.getByRole("textbox", { name: RepositoryFormLabels.Name })
    );
    await userEvent.clear(
      screen.getByRole("textbox", { name: RepositoryFormLabels.URL })
    );
    await userEvent.clear(
      screen.getByRole("textbox", { name: RepositoryFormLabels.Key })
    );
    await userEvent.clear(
      screen.getByRole("textbox", { name: RepositoryFormLabels.Distributions })
    );
    await userEvent.clear(
      screen.getByRole("textbox", { name: RepositoryFormLabels.Components })
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: RepositoryFormLabels.Name }),
      "newName"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: RepositoryFormLabels.URL }),
      "http://www.website.com"
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Save repository" })
    );

    expect(packageRepositoriesResolvers.updatePackageRepository.resolved).toBe(
      true
    );
  });

  it("can display a repository edit form with correct repo data", async () => {
    renderWithProviders(<EditRepository id={1} type="ppa" />, { state });

    await waitForLoading();

    const form = screen.getByRole("form", { name: "Edit PPA" });

    expect(form).toBeInTheDocument();
    expect(
      within(form).getByRole("textbox", { name: RepositoryFormLabels.Name })
    ).toBeInTheDocument();
  });

  it("sets disabled_components and disabled_pockets if the repo is a default repo", async () => {
    const mockRepo = factory.packageRepository({
      id: 1,
      name: "main_archive",
    });
    mockServer.use(
      packageRepositoriesResolvers.getPackageRepository.handler(mockRepo)
    );

    const mockMutate = spyOnMutation(
      repoQueryHooks,
      "useUpdatePackageRepository"
    );

    renderWithProviders(<EditRepository id={1} type="repository" />, { state });

    await waitForLoading();

    await userEvent.type(
      screen.getByRole("textbox", { name: "Key" }),
      "testing"
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Save repository" })
    );

    await waitFor(() => {
      expect(mockMutate).toHaveBeenCalledWith({
        headers: {
          ETag: null,
        },
        body: {
          arches: [],
          disable_sources: false,
          disabled_components: [],
          disabled_pockets: [],
          key: "testing",
          name: "Ubuntu archive",
          url: "test url",
        },
        path: {
          package_repository_id: 1,
        },
      });
    });
  });
});
