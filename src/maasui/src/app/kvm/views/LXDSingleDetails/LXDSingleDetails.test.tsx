import LXDSingleDetails from "./LXDSingleDetails";

import urls from "@/app/base/urls";
import { Label as LXDSingleResourcesLabel } from "@/app/kvm/views/LXDSingleDetails/LXDSingleResources/LXDSingleResources";
import { Label as LXDSingleSettingsLabel } from "@/app/kvm/views/LXDSingleDetails/LXDSingleSettings/LXDSingleSettings";
import { Label as LXDSingleVMsLabel } from "@/app/kvm/views/LXDSingleDetails/LXDSingleVMs/LXDSingleVMs";
import { PodType } from "@/app/store/pod/constants";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { poolsResolvers } from "@/testing/resolvers/pools";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  screen,
  renderWithProviders,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

setupMockServer(
  zoneResolvers.getZone.handler(),
  zoneResolvers.listZones.handler(),
  poolsResolvers.getPool.handler(),
  poolsResolvers.listPools.handler()
);

describe("LXDSingleDetails", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      pod: factory.podState({
        items: [factory.podDetails({ id: 1, type: PodType.LXD })],
        loaded: true,
      }),
      tag: factory.tagState({
        loaded: true,
      }),
    });
  });

  it(`Displays: ${LXDSingleVMsLabel.Title} at: ${urls.kvm.lxd.single.vms({ id: 1 })}`, async () => {
    renderWithProviders(<LXDSingleDetails />, {
      initialEntries: [urls.kvm.lxd.single.vms({ id: 1 })],
      state,
      pattern: `${urls.kvm.lxd.single.index(null)}/*`,
    });
    expect(screen.getByLabelText(LXDSingleVMsLabel.Title)).toBeInTheDocument();
  });

  it(`Displays: ${LXDSingleResourcesLabel.Title} at: ${urls.kvm.lxd.single.resources({ id: 1 })}`, async () => {
    renderWithProviders(<LXDSingleDetails />, {
      initialEntries: [urls.kvm.lxd.single.resources({ id: 1 })],
      state,
      pattern: `${urls.kvm.lxd.single.index(null)}/*`,
    });
    expect(
      screen.getByLabelText(LXDSingleResourcesLabel.Title)
    ).toBeInTheDocument();
  });

  it(`Displays: ${LXDSingleSettingsLabel.Title} at: ${urls.kvm.lxd.single.edit({ id: 1 })}`, async () => {
    renderWithProviders(<LXDSingleDetails />, {
      initialEntries: [urls.kvm.lxd.single.edit({ id: 1 })],
      state,
      pattern: `${urls.kvm.lxd.single.index(null)}/*`,
    });
    await waitFor(() => {
      expect(zoneResolvers.listZones.resolved).toBeTruthy();
    });
    expect(
      screen.getByLabelText(LXDSingleSettingsLabel.Title)
    ).toBeInTheDocument();
  });

  it("redirects to vms", async () => {
    const { router } = renderWithProviders(<LXDSingleDetails />, {
      initialEntries: [urls.kvm.lxd.single.index({ id: 1 })],
      state,
      pattern: `${urls.kvm.lxd.single.index(null)}/*`,
    });
    expect(router.state.location.pathname).toBe(
      urls.kvm.lxd.single.vms({ id: 1 })
    );
  });
});
