import { lazy } from "react";

import { createBrowserRouter, Navigate } from "react-router";

import Login from "./app/login/Login";
import LoginCallback from "./app/login/LoginCallback";
import RequireLogin from "./app/login/RequireLogin";
import GroupDetails from "./app/settings/views/UserManagement/views/Groups/views/GroupDetails";
import GroupsList from "./app/settings/views/UserManagement/views/Groups/views/GroupsList";
import TagDetails from "./app/tags/views/TagDetails";
import TagList from "./app/tags/views/TagList";

import App from "@/app/App";
import ErrorBoundary from "@/app/base/components/ErrorBoundary";
import PageContent from "@/app/base/components/PageContent";
import { useGetURLId } from "@/app/base/hooks/urls";
import urls from "@/app/base/urls";
import NotFound from "@/app/base/views/NotFound";
import machineUrls from "@/app/machines/urls";
import APIKeyList from "@/app/preferences/views/APIKeys/views";
import Details from "@/app/preferences/views/Details";
import SSHKeysList from "@/app/preferences/views/SSHKeys/views";
import SSLKeysList from "@/app/preferences/views/SSLKeys/views";
import Commissioning from "@/app/settings/views/Configuration/Commissioning";
import Deploy from "@/app/settings/views/Configuration/Deploy";
import General from "@/app/settings/views/Configuration/General";
import KernelParameters from "@/app/settings/views/Configuration/KernelParameters";
import DhcpList from "@/app/settings/views/Dhcp/DhcpList";
import ThirdPartyDrivers from "@/app/settings/views/Images/ThirdPartyDrivers";
import VMWare from "@/app/settings/views/Images/VMWare";
import Windows from "@/app/settings/views/Images/Windows";
import LicenseKeyList from "@/app/settings/views/LicenseKeys/views";
import DnsForm from "@/app/settings/views/Network/DnsForm";
import NtpForm from "@/app/settings/views/Network/NtpForm";
import ProxyForm from "@/app/settings/views/Network/ProxyForm";
import SyslogForm from "@/app/settings/views/Network/SyslogForm";
import RepositoriesList from "@/app/settings/views/Repositories/views";
import ScriptsList from "@/app/settings/views/Scripts/ScriptsList";
import IpmiSettings from "@/app/settings/views/Security/IpmiSettings";
import SecretStorage from "@/app/settings/views/Security/SecretStorage";
import SecurityProtocols from "@/app/settings/views/Security/SecurityProtocols";
import SessionTimeout from "@/app/settings/views/Security/SessionTimeout";
import StorageForm from "@/app/settings/views/Storage/StorageForm";
import SingleSignOn from "@/app/settings/views/UserManagement/views/SingleSignOn";
import UsersList from "@/app/settings/views/UserManagement/views/UsersList/UsersList";
import { MachineMeta } from "@/app/store/machine/types";
import { getRelativeRoute } from "@/app/utils";

const ControllerDetails = lazy(
  () => import("@/app/controllers/views/ControllerDetails")
);
const ControllerList = lazy(
  () => import("@/app/controllers/views/ControllerList")
);
const DeviceDetails = lazy(() => import("@/app/devices/views/DeviceDetails"));
const DeviceList = lazy(() => import("@/app/devices/views/DeviceList"));
const DomainDetails = lazy(() => import("@/app/domains/views/DomainDetails"));
const DomainsList = lazy(() => import("@/app/domains/views/DomainsList"));
const ImageList = lazy(() => import("@/app/images/views/ImageList"));
const Intro = lazy(() => import("@/app/intro/views/Intro"));
const KVMList = lazy(() => import("@/app/kvm/views/KVMList"));
const LXDClusterDetails = lazy(
  () => import("@/app/kvm/views/LXDClusterDetails")
);
const LXDSingleDetails = lazy(() => import("@/app/kvm/views/LXDSingleDetails"));
const VirshDetails = lazy(() => import("@/app/kvm/views/VirshDetails"));
const MachineDetails = lazy(
  () => import("@/app/machines/views/MachineDetails")
);
const MachineConfiguration = lazy(
  () => import("@/app/machines/views/MachineDetails/MachineConfiguration")
);
const MachineInstances = lazy(
  () => import("@/app/machines/views/MachineDetails/MachineInstances")
);
const MachineLogs = lazy(
  () => import("@/app/machines/views/MachineDetails/MachineLogs")
);
const MachineNetwork = lazy(
  () => import("@/app/machines/views/MachineDetails/MachineNetwork")
);
const NetworkNotifications = lazy(
  () =>
    import(
      "@/app/machines/views/MachineDetails/MachineNetwork/NetworkNotifications"
    )
);
const MachinePCIDevices = lazy(
  () => import("@/app/machines/views/MachineDetails/MachinePCIDevices")
);
const MachineScript = lazy(
  () => import("@/app/machines/views/MachineDetails/MachineScripts")
);
const MachineStorage = lazy(
  () => import("@/app/machines/views/MachineDetails/MachineStorage")
);
const StorageNotifications = lazy(
  () =>
    import(
      "@/app/machines/views/MachineDetails/MachineStorage/StorageNotifications"
    )
);
const MachineSummary = lazy(
  () => import("@/app/machines/views/MachineDetails/MachineSummary")
);
const SummaryNotifications = lazy(
  () =>
    import(
      "@/app/machines/views/MachineDetails/MachineSummary/SummaryNotifications"
    )
);
const MachineUSBDevices = lazy(
  () => import("@/app/machines/views/MachineDetails/MachineUSBDevices")
);
const Machines = lazy(() => import("@/app/machines/views/Machines"));
const DiscoveriesList = lazy(
  () => import("@/app/networkDiscovery/views/DiscoveriesList")
);
const NetworkDiscoverySettings = lazy(
  () => import("@/app/settings/views/Network/NetworkDiscoverySettings")
);
const Networks = lazy(() => import("@/app/networks"));
const PoolsList = lazy(() => import("@/app/pools/views/PoolsList"));
const RacksList = lazy(() => import("@/app/racks/views/RacksList"));
const SwitchesList = lazy(() => import("@/app/switches/views/SwitchesList"));
const Settings = lazy(() => import("@/app/settings/views/Settings"));
const FabricDetails = lazy(
  () => import("@/app/networks/views/Fabrics/views/FabricDetails")
);
const FabricsList = lazy(
  () => import("@/app/networks/views/Fabrics/views/FabricsList")
);
const Sources = lazy(() => import("@/app/settings/views/Images/Sources"));
const SpaceDetails = lazy(
  () => import("@/app/networks/views/Spaces/views/SpaceDetails")
);
const SpacesList = lazy(
  () => import("@/app/networks/views/Spaces/views/SpacesList")
);
const SubnetDetails = lazy(
  () => import("@/app/networks/views/Subnets/views/SubnetDetails")
);
const SubnetsList = lazy(
  () => import("@/app/networks/views/Subnets/views/SubnetsList")
);
const Synchronization = lazy(
  () => import("@/app/settings/views/Images/Synchronization")
);
const VLANDetails = lazy(
  () => import("@/app/networks/views/VLANs/views/VLANDetails")
);
const VLANsList = lazy(
  () => import("@/app/networks/views/VLANs/views/VLANsList")
);
const ZonesList = lazy(() => import("@/app/zones/views"));

const MachineRedirect = ({
  to,
}: {
  to: (params: { id: string }) => string;
}): React.ReactElement | null => {
  const id = useGetURLId(MachineMeta.PK);
  if (!id) return null;
  return <Navigate replace to={to({ id })} />;
};

export const router = createBrowserRouter(
  [
    {
      path: "/",
      element: <App />,
      children: [
        {
          path: urls.login,
          element: <Login />,
        },
        {
          path: urls.loginCallback,
          element: <LoginCallback />,
        },
        {
          element: <RequireLogin />,
          children: [
            {
              path: urls.index,
              element: <Navigate replace to={urls.machines.index} />,
            },
            {
              path: urls.machines.index,
              element: (
                <ErrorBoundary>
                  <Machines />
                </ErrorBoundary>
              ),
            },
            {
              path: `${urls.zones.index}`,
              element: (
                <ErrorBoundary>
                  <ZonesList />
                </ErrorBoundary>
              ),
            },
            {
              path: urls.networkDiscovery.index,
              element: (
                <ErrorBoundary>
                  <DiscoveriesList />
                </ErrorBoundary>
              ),
            },
            {
              path: urls.networkDiscovery.legacyIndex,
              element: <Navigate replace to={urls.networkDiscovery.index} />,
            },
            {
              path: urls.networkDiscovery.legacyConfiguration,
              element: (
                <Navigate replace to={urls.networkDiscovery.configuration} />
              ),
            },
            {
              path: `${urls.devices.index}/*`,
              element: (
                <ErrorBoundary>
                  <DeviceList />
                </ErrorBoundary>
              ),
            },
            {
              path: `${urls.devices.device.index(null)}/*`,
              element: (
                <ErrorBoundary>
                  <DeviceDetails />
                </ErrorBoundary>
              ),
            },
            {
              path: `${urls.domains.index}/*`,
              element: (
                <ErrorBoundary>
                  <DomainsList />
                </ErrorBoundary>
              ),
            },
            {
              path: `${urls.domains.details(null)}/*`,
              element: (
                <ErrorBoundary>
                  <DomainDetails />
                </ErrorBoundary>
              ),
            },
            {
              path: `${urls.tags.index}/*`,
              element: (
                <ErrorBoundary>
                  <TagList />
                </ErrorBoundary>
              ),
            },
            {
              path: `${urls.tags.tag.index(null)}/*`,
              element: (
                <ErrorBoundary>
                  <TagDetails />
                </ErrorBoundary>
              ),
            },
            {
              path: `${urls.networks.space.index(null)}/*`,
              element: (
                <ErrorBoundary>
                  <SpaceDetails />
                </ErrorBoundary>
              ),
            },
            {
              path: `${urls.settings.index}/*`,
              element: (
                <ErrorBoundary>
                  <Settings />
                </ErrorBoundary>
              ),
            },
            {
              path: `${urls.intro.index}/*`,
              element: (
                <ErrorBoundary>
                  <Intro />
                </ErrorBoundary>
              ),
            },
            {
              path: `${urls.images.index}/*`,
              element: (
                <ErrorBoundary>
                  <ImageList />
                </ErrorBoundary>
              ),
            },
            {
              path: urls.preferences.index,
              children: [
                {
                  path: urls.preferences.index,
                  element: <Navigate replace to={urls.preferences.details} />,
                },
                {
                  path: getRelativeRoute(
                    urls.preferences.details,
                    urls.preferences.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <PageContent aria-label={"My preferences"}>
                        <Details />
                      </PageContent>
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.preferences.apiKeys.index,
                    urls.preferences.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <APIKeyList />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.preferences.sshKeys,
                    urls.preferences.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <SSHKeysList />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.preferences.sslKeys,
                    urls.preferences.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <SSLKeysList />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute("*", urls.preferences.index),
                  element: <NotFound />,
                },
              ],
            },
            {
              path: urls.machines.machine.index(null),
              element: (
                <ErrorBoundary>
                  <MachineDetails />
                </ErrorBoundary>
              ),
              children: [
                {
                  index: true,
                  element: <MachineRedirect to={machineUrls.machine.summary} />,
                },
                {
                  path: getRelativeRoute(
                    machineUrls.machine.summary(null),
                    machineUrls.machine.index(null)
                  ),
                  element: (
                    <>
                      <SummaryNotifications />
                      <MachineSummary />
                    </>
                  ),
                },
                {
                  path: getRelativeRoute(
                    machineUrls.machine.instances(null),
                    machineUrls.machine.index(null)
                  ),
                  element: <MachineInstances />,
                },
                {
                  path: getRelativeRoute(
                    machineUrls.machine.network(null),
                    machineUrls.machine.index(null)
                  ),
                  element: (
                    <>
                      <NetworkNotifications />
                      <MachineNetwork />
                    </>
                  ),
                },
                {
                  path: getRelativeRoute(
                    machineUrls.machine.storage(null),
                    machineUrls.machine.index(null)
                  ),
                  element: (
                    <>
                      <StorageNotifications />
                      <MachineStorage />
                    </>
                  ),
                },
                {
                  path: getRelativeRoute(
                    machineUrls.machine.pciDevices(null),
                    machineUrls.machine.index(null)
                  ),
                  element: <MachinePCIDevices />,
                },
                {
                  path: getRelativeRoute(
                    machineUrls.machine.usbDevices(null),
                    machineUrls.machine.index(null)
                  ),
                  element: <MachineUSBDevices />,
                },
                {
                  path: `${getRelativeRoute(
                    machineUrls.machine.scriptsResults.index(null),
                    machineUrls.machine.index(null)
                  )}/*`,
                  element: <MachineScript />,
                },
                {
                  path: getRelativeRoute(
                    machineUrls.machine.commissioning.index(null),
                    machineUrls.machine.index(null)
                  ),
                  element: (
                    <MachineRedirect
                      to={
                        machineUrls.machine.scriptsResults.commissioning.index
                      }
                    />
                  ),
                },
                {
                  path: `${getRelativeRoute(
                    machineUrls.machine.logs.index(null),
                    machineUrls.machine.index(null)
                  )}/*`,
                  element: <MachineLogs />,
                },
                {
                  path: getRelativeRoute(
                    machineUrls.machine.events(null),
                    machineUrls.machine.index(null)
                  ),
                  element: (
                    <MachineRedirect to={machineUrls.machine.logs.events} />
                  ),
                },
                {
                  path: getRelativeRoute(
                    machineUrls.machine.configuration(null),
                    machineUrls.machine.index(null)
                  ),
                  element: <MachineConfiguration />,
                },
              ],
            },
            {
              path: `${urls.networks.fabric.index(null)}/*`,
              element: (
                <ErrorBoundary>
                  <FabricDetails />
                </ErrorBoundary>
              ),
            },
            {
              path: `${urls.controllers.controller.index(null)}/*`,
              element: (
                <ErrorBoundary>
                  <ControllerDetails />
                </ErrorBoundary>
              ),
            },
            {
              path: `${urls.controllers.index}/*`,
              element: (
                <ErrorBoundary>
                  <ControllerList />
                </ErrorBoundary>
              ),
            },
            {
              path: urls.kvm.index,
              children: [
                {
                  path: urls.kvm.index,
                  element: <Navigate replace to={urls.kvm.lxd.index} />,
                },
                {
                  path: getRelativeRoute(urls.kvm.lxd.index, urls.kvm.index),
                  element: (
                    <ErrorBoundary>
                      <KVMList />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(urls.kvm.virsh.index, urls.kvm.index),
                  element: (
                    <ErrorBoundary>
                      <KVMList />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: `${getRelativeRoute(
                    urls.kvm.lxd.cluster.index(null),
                    urls.kvm.index
                  )}/*`,
                  element: (
                    <ErrorBoundary>
                      <LXDClusterDetails />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: `${getRelativeRoute(
                    urls.kvm.lxd.single.index(null),
                    urls.kvm.index
                  )}/*`,
                  element: (
                    <ErrorBoundary>
                      <LXDSingleDetails />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: `${getRelativeRoute(
                    urls.kvm.virsh.details.index(null),
                    urls.kvm.index
                  )}/*`,
                  element: (
                    <ErrorBoundary>
                      <VirshDetails />
                    </ErrorBoundary>
                  ),
                },
              ],
            },
            {
              path: `${urls.pools.index}/*`,
              element: (
                <ErrorBoundary>
                  <PoolsList />
                </ErrorBoundary>
              ),
            },
            {
              path: urls.networks.index,
              element: <Networks />,
              children: [
                {
                  path: `${urls.networks.index}`,
                  element: (
                    <Navigate replace to={urls.networks.subnets.index} />
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.networks.subnets.index,
                    urls.networks.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <SubnetsList />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.networks.spaces.index,
                    urls.networks.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <SpacesList />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.networks.fabrics.index,
                    urls.networks.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <FabricsList />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.networks.vlans.index,
                    urls.networks.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <VLANsList />
                    </ErrorBoundary>
                  ),
                },
              ],
            },
            {
              path: `${urls.networks.subnet.index(null)}/*`,
              element: (
                <ErrorBoundary>
                  <SubnetDetails />
                </ErrorBoundary>
              ),
            },
            {
              path: `${urls.networks.vlan.index(null)}/*`,
              element: (
                <ErrorBoundary>
                  <VLANDetails />
                </ErrorBoundary>
              ),
            },
            {
              path: `${urls.racks.index}/*`,
              element: (
                <ErrorBoundary>
                  <RacksList />
                </ErrorBoundary>
              ),
            },
            {
              path: `${urls.switches.index}/*`,
              element: (
                <ErrorBoundary>
                  <SwitchesList />
                </ErrorBoundary>
              ),
            },
            {
              path: urls.settings.index,
              element: <Settings />,
              children: [
                {
                  path: urls.settings.index,
                  element: (
                    <Navigate replace to={urls.settings.configuration.index} />
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.configuration.index,
                    urls.settings.index
                  ),
                  element: (
                    <Navigate
                      replace
                      to={urls.settings.configuration.general}
                    />
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.security.index,
                    urls.settings.index
                  ),
                  element: (
                    <Navigate
                      replace
                      to={urls.settings.security.securityProtocols}
                    />
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.network.index,
                    urls.settings.index
                  ),
                  element: (
                    <Navigate replace to={urls.settings.network.proxy} />
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.configuration.general,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <General />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.configuration.commissioning,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <Commissioning />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.configuration.kernelParameters,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <KernelParameters />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.configuration.deploy,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <Deploy />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.security.securityProtocols,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <SecurityProtocols />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.security.secretStorage,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <SecretStorage />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.security.sessionTimeout,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <SessionTimeout />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.security.ipmiSettings,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <IpmiSettings />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.userManagement.users,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <UsersList />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.userManagement.groups,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <GroupsList />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: `${urls.settings.userManagement.group.index(null)}/*`,
                  element: (
                    <ErrorBoundary>
                      <GroupDetails />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.userManagement.singleSignOn,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <SingleSignOn />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.licenseKeys.index,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <LicenseKeyList />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.storage,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <StorageForm />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.network.proxy,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <ProxyForm />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.network.dns,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <DnsForm />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.network.ntp,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <NtpForm />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.network.syslog,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <SyslogForm />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.network.networkDiscovery,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <NetworkDiscoverySettings />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.scripts.commissioning.index,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <PageContent>
                        <ScriptsList type="commissioning" />
                      </PageContent>
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.scripts.testing.index,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <PageContent>
                        <ScriptsList type="testing" />
                      </PageContent>
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.scripts.deploying.index,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <PageContent>
                        <ScriptsList type="deployment" />
                      </PageContent>
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.dhcp.index,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <PageContent>
                        <DhcpList />
                      </PageContent>
                    </ErrorBoundary>
                  ),
                },

                {
                  path: getRelativeRoute(
                    urls.settings.repositories.index,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <RepositoriesList />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.images.windows,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <Windows />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.images.vmware,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <VMWare />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.images.ubuntu,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <ThirdPartyDrivers />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.images.sources,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <Sources />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute(
                    urls.settings.images.sync,
                    urls.settings.index
                  ),
                  element: (
                    <ErrorBoundary>
                      <Synchronization />
                    </ErrorBoundary>
                  ),
                },
                {
                  path: getRelativeRoute("*", urls.settings.index),
                  element: <NotFound />,
                },
              ],
            },
          ],
        },
        {
          path: "*",
          element: <NotFound includeSection />,
        },
      ],
    },
  ],
  {
    basename: `${import.meta.env.VITE_APP_BASENAME}${
      import.meta.env.VITE_APP_VITE_BASENAME
    }`,
  }
);
