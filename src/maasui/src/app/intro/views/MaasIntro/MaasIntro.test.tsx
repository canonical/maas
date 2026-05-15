import { waitFor } from "@testing-library/react";

import { Labels as ConnectivityCardLabels } from "./ConnectivityCard/ConnectivityCard";
import MaasIntro, { Labels as MaasIntroLabels } from "./MaasIntro";
import { Labels as NameCardLabels } from "./NameCard/NameCard";

import { configActions } from "@/app/store/config";
import { ConfigNames } from "@/app/store/config/types";
import { repositoryActions } from "@/app/store/packagerepository";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
} from "@/testing/utils";

setupMockServer(
  authResolvers.getCurrentUser.handler(factory.user({ is_superuser: true })),
  authResolvers.getMeStatistics.handler(
    factory.userStatistics({ completed_intro: false })
  )
);

describe("MaasIntro", () => {
  let state: RootState;
  const mainArchive = factory.packageRepository({
    default: true,
    name: "main_archive",
    url: "http://www.mainarchive.com",
  });
  const portsArchive = factory.packageRepository({
    default: true,
    name: "ports_archive",
    url: "http://www.portsarchive.com",
  });

  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        items: [
          factory.config({ name: ConfigNames.COMPLETED_INTRO, value: false }),
          factory.config({ name: ConfigNames.MAAS_NAME, value: "bionic-maas" }),
          factory.config({
            name: ConfigNames.HTTP_PROXY,
            value: "http://www.site.com",
          }),
          factory.config({ name: ConfigNames.UPSTREAM_DNS, value: "8.8.8.8" }),
        ],
      }),
      packagerepository: factory.packageRepositoryState({
        items: [mainArchive, portsArchive],
      }),
    });
  });

  it("displays a spinner when loading", () => {
    state.config.loading = true;
    renderWithProviders(<MaasIntro />, {
      initialEntries: ["/intro"],
      state,
    });
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("can update just the config", async () => {
    const { store } = renderWithProviders(<MaasIntro />, {
      state,
      initialEntries: ["/intro"],
    });
    await waitFor(() => {
      expect(
        screen.getByRole("textbox", { name: NameCardLabels.Name })
      ).toBeInTheDocument();
    });
    const name = screen.getByRole("textbox", { name: NameCardLabels.Name });
    const proxy = screen.getByRole("textbox", {
      name: ConnectivityCardLabels.HttpProxy,
    });
    const upstream_dns = screen.getByRole("textbox", {
      name: ConnectivityCardLabels.UpstreamDns,
    });

    await userEvent.clear(name);
    await userEvent.clear(proxy);
    await userEvent.clear(upstream_dns);

    await userEvent.type(name, "my new maas");
    await userEvent.type(proxy, "http://www.newproxy.com");
    await userEvent.type(upstream_dns, "0.0.0.0");

    await userEvent.click(
      screen.getByRole("button", { name: MaasIntroLabels.SubmitLabel })
    );
    const updateConfigAction = configActions.update({
      http_proxy: "http://www.newproxy.com",
      maas_name: "my new maas",
      upstream_dns: "0.0.0.0",
    });
    const updateRepoAction = repositoryActions.update(mainArchive);
    expect(
      store
        .getActions()
        .find((action) => action.type === updateConfigAction.type)
    ).toStrictEqual(updateConfigAction);
    expect(
      store
        .getActions()
        .filter((action) => action.type === updateRepoAction.type).length
    ).toBe(0);
  });

  it("can dispatch actions to update the default package repository urls", async () => {
    const { store } = renderWithProviders(<MaasIntro />, {
      state,
      initialEntries: ["/intro"],
    });
    await waitFor(() => {
      expect(
        screen.getByRole("textbox", { name: NameCardLabels.Name })
      ).toBeInTheDocument();
    });
    const name = screen.getByRole("textbox", { name: NameCardLabels.Name });
    const proxy = screen.getByRole("textbox", {
      name: ConnectivityCardLabels.HttpProxy,
    });
    const upstreamDnsField = screen.getByRole("textbox", {
      name: ConnectivityCardLabels.UpstreamDns,
    });
    const mainArchiveField = screen.getByRole("textbox", {
      name: ConnectivityCardLabels.MainArchiveUrl,
    });
    const portsArchiveField = screen.getByRole("textbox", {
      name: ConnectivityCardLabels.PortsArchiveUrl,
    });

    await userEvent.clear(name);
    await userEvent.clear(proxy);
    await userEvent.clear(upstreamDnsField);
    await userEvent.clear(mainArchiveField);
    await userEvent.clear(portsArchiveField);

    await userEvent.type(name, "my new maas");
    await userEvent.type(proxy, "http://localhost:3000");
    await userEvent.type(upstreamDnsField, "0.0.0.0");
    await userEvent.type(mainArchiveField, "http://www.newmainarchive.com");
    await userEvent.type(portsArchiveField, "http://www.newportsarchive.com");

    await userEvent.click(
      screen.getByRole("button", { name: MaasIntroLabels.SubmitLabel })
    );

    const updateMainArchiveAction = repositoryActions.update({
      id: mainArchive.id,
      name: mainArchive.name,
      url: "http://www.newmainarchive.com",
    });
    const updatePortsArchiveAction = repositoryActions.update({
      id: portsArchive.id,
      name: portsArchive.name,
      url: "http://www.newportsarchive.com",
    });
    const updateRepoActions = store
      .getActions()
      .filter((action) => action.type === updateMainArchiveAction.type);

    expect(updateRepoActions.length).toBe(2);
    expect(updateRepoActions[0]).toStrictEqual(updateMainArchiveAction);
    expect(updateRepoActions[1]).toStrictEqual(updatePortsArchiveAction);
  });

  it("can skip the initial MAAS setup", async () => {
    const { store } = renderWithProviders(<MaasIntro />, {
      state,
      initialEntries: ["/intro"],
    });
    await waitFor(() => {
      expect(
        screen.queryByText(MaasIntroLabels.AreYouSure)
      ).not.toBeInTheDocument();
    });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: MaasIntroLabels.SecondarySubmit })
      ).toBeInTheDocument();
    });

    // Open the skip confirmation.
    await userEvent.click(
      screen.getByRole("button", { name: MaasIntroLabels.SecondarySubmit })
    );

    expect(screen.getByText(MaasIntroLabels.AreYouSure)).toBeInTheDocument();

    // Confirm skipping MAAS setup.
    await userEvent.click(
      screen.getByRole("button", { name: MaasIntroLabels.SkipToUserSetup })
    );
    const expectedAction = configActions.update({
      completed_intro: true,
    });
    const actualAction = store
      .getActions()
      .find((action) => action.type === expectedAction.type);

    expect(actualAction).toStrictEqual(expectedAction);
  });
});
