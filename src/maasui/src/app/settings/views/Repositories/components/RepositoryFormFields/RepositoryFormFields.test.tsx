import { AddRepository, EditRepository } from "../../components";

import { Labels as RepositoryFormLabels } from "./RepositoryFormFields";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { packageRepositoriesResolvers } from "@/testing/resolvers/packageRepositories";
import {
  screen,
  within,
  renderWithProviders,
  setupMockServer,
  waitForLoading,
} from "@/testing/utils";

describe("RepositoryFormFields", () => {
  let state: RootState;

  const mockServer = setupMockServer(
    packageRepositoriesResolvers.getPackageRepository.handler()
  );

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

  it("displays distribution and component inputs if type is repository", async () => {
    renderWithProviders(<AddRepository type="repository" />, { state });

    expect(
      screen.getByRole("textbox", { name: RepositoryFormLabels.Distributions })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("textbox", { name: RepositoryFormLabels.Components })
    ).toBeInTheDocument();
  });

  it("doesn't display distribution and component inputs if type is ppa", async () => {
    renderWithProviders(<AddRepository type="ppa" />, {
      state,
    });

    await waitForLoading();
    expect(
      screen.queryByRole("textbox", {
        name: RepositoryFormLabels.Distributions,
      })
    ).not.toBeInTheDocument();

    expect(
      screen.queryByRole("textbox", { name: RepositoryFormLabels.Components })
    ).not.toBeInTheDocument();
  });

  it("doesn't display disabled pockets checkboxes if repository is not default", async () => {
    state.general.pocketsToDisable.data = ["updates", "security", "backports"];
    const mockRepo = factory.packageRepository({
      name: "not default",
      disabled_pockets: ["updates"],
    });
    mockServer.use(
      packageRepositoriesResolvers.getPackageRepository.handler(mockRepo)
    );

    renderWithProviders(<EditRepository id={mockRepo.id} type="repository" />, {
      state,
    });

    await waitForLoading();

    expect(
      screen.queryByRole("list", { name: RepositoryFormLabels.DisabledPockets })
    ).not.toBeInTheDocument();
  });

  it("displays disabled pockets checkboxes if repository is default", async () => {
    state.general.pocketsToDisable.data = ["updates", "security", "backports"];
    const mockRepo = factory.packageRepository({
      name: "main_archive",
      disabled_pockets: ["updates"],
    });
    mockServer.use(
      packageRepositoriesResolvers.getPackageRepository.handler(mockRepo)
    );

    renderWithProviders(<EditRepository id={mockRepo.id} type="repository" />, {
      state,
    });

    await waitForLoading();

    const disabled_pockets_list = screen.getByRole("list", {
      name: RepositoryFormLabels.DisabledPockets,
    });
    expect(disabled_pockets_list).toBeInTheDocument();
    expect(within(disabled_pockets_list).getAllByRole("checkbox").length).toBe(
      3
    );
  });

  it("doesn't display disabled components checkboxes if repository is not default", async () => {
    state.general.componentsToDisable.data = [
      "restricted",
      "universe",
      "multiverse",
    ];
    const mockRepo = factory.packageRepository({
      name: "not default",
      disabled_pockets: ["universe"],
    });
    mockServer.use(
      packageRepositoriesResolvers.getPackageRepository.handler(mockRepo)
    );

    renderWithProviders(<EditRepository id={mockRepo.id} type="repository" />, {
      state,
    });

    await waitForLoading();
    expect(
      screen.queryByRole("list", {
        name: RepositoryFormLabels.DisabledComponents,
      })
    ).not.toBeInTheDocument();
  });

  it("displays disabled components checkboxes if repository is default", async () => {
    state.general.componentsToDisable.data = [
      "restricted",
      "universe",
      "multiverse",
    ];
    const mockRepo = factory.packageRepository({
      name: "main_archive",
      disabled_pockets: ["universe"],
    });
    mockServer.use(
      packageRepositoriesResolvers.getPackageRepository.handler(mockRepo)
    );

    renderWithProviders(<EditRepository id={mockRepo.id} type="repository" />, {
      state,
    });

    await waitForLoading();

    const disabled_components_list = screen.getByRole("list", {
      name: RepositoryFormLabels.DisabledComponents,
    });
    expect(disabled_components_list).toBeInTheDocument();
    expect(
      within(disabled_components_list).getAllByRole("checkbox").length
    ).toBe(3);
  });

  it("correctly reflects repository name", async () => {
    const mockRepo = factory.packageRepository({
      name: "repo-name",
    });
    mockServer.use(
      packageRepositoriesResolvers.getPackageRepository.handler(mockRepo)
    );

    renderWithProviders(<EditRepository id={mockRepo.id} type="repository" />, {
      state,
    });

    await waitForLoading();

    expect(
      screen.getByRole("textbox", { name: RepositoryFormLabels.Name })
    ).toHaveValue("repo-name");
  });

  it("correctly reflects repository url", async () => {
    const mockRepo = factory.packageRepository({
      url: "fake.url",
    });
    mockServer.use(
      packageRepositoriesResolvers.getPackageRepository.handler(mockRepo)
    );

    renderWithProviders(<EditRepository id={mockRepo.id} type="repository" />, {
      state,
    });

    await waitForLoading();

    expect(
      screen.getByRole("textbox", { name: RepositoryFormLabels.URL })
    ).toHaveValue("fake.url");
  });

  it("correctly reflects repository key", async () => {
    const mockRepo = factory.packageRepository({
      key: "fake-key",
    });
    mockServer.use(
      packageRepositoriesResolvers.getPackageRepository.handler(mockRepo)
    );

    renderWithProviders(<EditRepository id={mockRepo.id} type="repository" />, {
      state,
    });

    await waitForLoading();

    expect(
      screen.getByRole("textbox", { name: RepositoryFormLabels.Key })
    ).toHaveValue("fake-key");
  });

  it("correctly reflects repository enabled state", async () => {
    const mockRepo = factory.packageRepository({
      enabled: false,
    });
    mockServer.use(
      packageRepositoriesResolvers.getPackageRepository.handler(mockRepo)
    );

    renderWithProviders(<EditRepository id={mockRepo.id} type="repository" />, {
      state,
    });

    await waitForLoading();

    expect(
      screen.getAllByRole("checkbox", {
        name: RepositoryFormLabels.EnableRepo,
      })[0]
    ).not.toBeChecked();
  });

  it("correctly reflects repository disable_sources state by displaying the inverse", async () => {
    const mockRepo = factory.packageRepository({
      disable_sources: false,
    });
    mockServer.use(
      packageRepositoriesResolvers.getPackageRepository.handler(mockRepo)
    );

    renderWithProviders(<EditRepository id={mockRepo.id} type="repository" />, {
      state,
    });

    await waitForLoading();

    expect(
      screen.getAllByRole("checkbox", {
        name: RepositoryFormLabels.EnableSources,
      })[0]
    ).toBeChecked();
  });

  it("correctly reflects repository arches", async () => {
    state.general.knownArchitectures.data = ["amd64", "i386", "ppc64el"];
    const mockRepo = factory.packageRepository({
      arches: ["amd64", "ppc64el"],
    });
    mockServer.use(
      packageRepositoriesResolvers.getPackageRepository.handler(mockRepo)
    );

    renderWithProviders(<EditRepository id={mockRepo.id} type="repository" />, {
      state,
    });

    await waitForLoading();

    const arches_list = screen.getByRole("list", {
      name: RepositoryFormLabels.Arches,
    });
    const arches_list_items = within(arches_list).getAllByRole("checkbox");

    expect(arches_list).toBeInTheDocument();

    expect(arches_list_items.length).toBe(3);
    expect(arches_list_items[0]).toBeChecked();
    expect(arches_list_items[1]).not.toBeChecked();
    expect(arches_list_items[2]).toBeChecked();
  });

  it("correctly reflects repository disabled_pockets", async () => {
    state.general.pocketsToDisable.data = ["updates", "security", "backports"];
    const mockRepo = factory.packageRepository({
      name: "main_archive",
      disabled_pockets: ["updates"],
    });
    mockServer.use(
      packageRepositoriesResolvers.getPackageRepository.handler(mockRepo)
    );

    renderWithProviders(<EditRepository id={mockRepo.id} type="repository" />, {
      state,
    });

    await waitForLoading();

    const disabled_pockets_list = within(
      screen.getByRole("list", {
        name: RepositoryFormLabels.DisabledPockets,
      })
    ).getAllByRole("checkbox");

    expect(disabled_pockets_list.length).toBe(3);
    expect(disabled_pockets_list[0]).toBeChecked();
    expect(disabled_pockets_list[1]).not.toBeChecked();
    expect(disabled_pockets_list[2]).not.toBeChecked();
  });

  it("correctly reflects repository disabled_components", async () => {
    state.general.componentsToDisable.data = [
      "restricted",
      "universe",
      "multiverse",
    ];
    const mockRepo = factory.packageRepository({
      name: "main_archive",
      disabled_components: ["universe"],
    });
    mockServer.use(
      packageRepositoriesResolvers.getPackageRepository.handler(mockRepo)
    );

    renderWithProviders(<EditRepository id={mockRepo.id} type="repository" />, {
      state,
    });

    await waitForLoading();

    const disabled_components_list = within(
      screen.getByRole("list", {
        name: RepositoryFormLabels.DisabledComponents,
      })
    ).getAllByRole("checkbox");

    expect(disabled_components_list.length).toBe(3);
    expect(disabled_components_list[0]).not.toBeChecked();
    expect(disabled_components_list[1]).toBeChecked();
    expect(disabled_components_list[2]).not.toBeChecked();
  });
});
