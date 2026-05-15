import { createSelector } from "@reduxjs/toolkit";

import type { Days, TimeSpan } from "@/app/base/types";
import type {
  AutoIpmiPrivilegeLevel,
  Config,
  ConfigState,
  ConfigValues,
  NetworkDiscovery,
} from "@/app/store/config/types";
import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import type { StorageLayout } from "@/app/store/types/enum";
/**
 * Returns value of an object in an array, given a certain name.
 * @param {Config[]} arr - Array to search for name.
 * @param {Config["name"]} name - Name paramenter of the object to search for.
 * @returns Value parameter of found object.
 */
const getValueFromName = <V extends ConfigValues>(
  arr: Config<ConfigValues>[],
  name: Config<V>["name"]
): Config<V>["value"] | null => {
  const found = arr.find((item) => item.name === name);
  if (found) {
    return found.value as V;
  }
  return null;
};

type Option = {
  label: string;
  value: number | string;
};

/**
 * Returns choices of an object in an array, given a certain name.
 * @param arr - Array to search for name.
 * @param name - Name paramenter of the object to search for.
 * @returns Available choices.
 */
const getOptionsFromName = <V extends ConfigValues>(
  arr: Config<ConfigValues>[],
  name: Config<V>["name"]
): Option[] | null => {
  const found = arr.find((item) => item.name === name);
  if (found && found.choices) {
    return found.choices.map((choice) => ({
      value: choice[0],
      label: choice[1],
    }));
  }
  return null;
};

/**
 * The config slice of state.
 * @param state - The redux state.
 * @returns The config state.
 */
const configState = (state: RootState): ConfigState => state.config;

/**
 * Returns the config errors.
 * @param state - The redux state.
 * @returns Config errors.
 */
const errors = createSelector([configState], (config) => config.errors);

/**
 * Returns list of all MAAS configs
 * @param state - The redux state.
 * @returns {Config[]} A list of all state.config.items.
 */
const all = (state: RootState): Config<ConfigValues>[] => state.config.items;

/**
 * Returns true if config is loading.
 * @param state - The redux state.
 * @returns {ConfigState["loading"]} Config is loading.
 */
const loading = (state: RootState): boolean => state.config.loading;

/**
 * Returns true if config has been loaded.
 * @param state - The redux state.
 * @returns {ConfigState["loaded"]} Config has loaded.
 */
const loaded = (state: RootState): boolean => state.config.loaded;

/**
 * Returns true if config is saving.
 * @param state - The redux state.
 * @returns {ConfigState["saving"]} Config is saving.
 */
const saving = (state: RootState): boolean => state.config.saving;

/**
 * Returns true if config has saved.
 * @param state - The redux state.
 * @returns {ConfigState["saved"]} Config has saved.
 */
const saved = (state: RootState): boolean => state.config.saved;

/**
 * Returns the MAAS config for default storage layout.
 * @param state - The redux state.
 * @returns Default storage layout.
 */
const defaultStorageLayout = createSelector([all], (configs) =>
  getValueFromName<StorageLayout>(configs, ConfigNames.DEFAULT_STORAGE_LAYOUT)
);

/**
 * Returns the possible storage layout options reformatted as objects.
 * @param state - The redux state.
 * @returns {Option[]} Storage layout options.
 */
const storageLayoutOptions = createSelector([all], (configs) =>
  getOptionsFromName<string>(configs, ConfigNames.DEFAULT_STORAGE_LAYOUT)
);

/**
 * Returns the MAAS config for enabling disk erase on release.
 * @param state - The redux state.
 * @returns Enable disk erasing on release.
 */
const enableDiskErasing = createSelector([all], (configs) =>
  getValueFromName<boolean>(configs, ConfigNames.ENABLE_DISK_ERASING_ON_RELEASE)
);

/**
 * Returns the MAAS config for enabling disk erase with secure erase.
 * @param state - The redux state.
 * @returns Enable disk erasing with secure erase.
 */
const diskEraseWithSecure = createSelector([all], (configs) =>
  getValueFromName<boolean>(configs, ConfigNames.DISK_ERASE_WITH_SECURE_ERASE)
);

/**
 * Returns the MAAS config for enabling disk erase with quick erase.
 * @param state - The redux state.
 * @returns Enable disk erasing with quick erase.
 */
const diskEraseWithQuick = createSelector([all], (configs) =>
  getValueFromName<boolean>(configs, ConfigNames.DISK_ERASE_WITH_QUICK_ERASE)
);

/**
 * Returns the MAAS config for http proxy url.
 * @param state - The redux state.
 * @returns HTTP proxy.
 */
const httpProxy = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.HTTP_PROXY)
);

/**
 * Returns the MAAS config for enabling http proxy.
 * @param state - The redux state.
 * @returns Enable HTTP proxy.
 */
const enableHttpProxy = createSelector([all], (configs) =>
  getValueFromName<boolean>(configs, ConfigNames.ENABLE_HTTP_PROXY)
);

/**
 * Returns the MAAS config for using peer proxy.
 * @param state - The redux state.
 * @returns Use peer proxy.
 */
const usePeerProxy = createSelector([all], (configs) =>
  getValueFromName<boolean>(configs, ConfigNames.USE_PEER_PROXY)
);

/**
 * Returns the proxy type, given other proxy config.
 * @param state - The redux state.
 * @returns {String} Proxy type.
 */
const proxyType = createSelector(
  [httpProxy, enableHttpProxy, usePeerProxy],
  (httpProxy, enableHttpProxy, usePeerProxy) => {
    if (enableHttpProxy) {
      if (httpProxy) {
        if (usePeerProxy) {
          return "peerProxy";
        } else {
          return "externalProxy";
        }
      } else {
        return "builtInProxy";
      }
    }
    return "noProxy";
  }
);

/**
 * Returns the MAAS config for MAAS name.
 * @param - The redux state.
 * @returns Then MAAS name.
 */
const maasName = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.MAAS_NAME)
);

/**
 * Returns the MAAS config for MAAS theme.
 * @param - The redux state
 * @returns The MAAS theme.
 */
const theme = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.THEME)
);

/**
 * Returns the MAAS config for session length.
 * @param - The redux state
 * @returns The MAAS session length in seconds.
 */
const sessionLength = createSelector([all], (configs) =>
  getValueFromName<number>(configs, ConfigNames.SESSION_LENGTH)
);

/**
 * Returns the MAAS config for MAAS uuid.
 * @param - The redux state.
 * @returns Then MAAS uuid.
 */
const uuid = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.UUID)
);

/**
 * Returns the MAAS config for enable analytics.
 * @param - The redux state.
 * @returns Enable analytics.
 */
const analyticsEnabled = createSelector([all], (configs) =>
  getValueFromName<boolean>(configs, ConfigNames.ENABLE_ANALYTICS)
);

/**
 * Returns the MAAS config for default distro series.
 * @param state - The redux state.
 * @returns Default distro series.
 */
const commissioningDistroSeries = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.COMMISSIONING_DISTRO_SERIES)
);

/**
 * Returns the possible distro series options reformatted as objects.
 * @param state - The redux state.
 * @returns {Option[]} Distro series options.
 */
const distroSeriesOptions = createSelector([all], (configs) =>
  getOptionsFromName<string>(configs, ConfigNames.COMMISSIONING_DISTRO_SERIES)
);

/**
 * Returns the MAAS config for default min kernel version.
 * @param state - The redux state.
 * @returns Default min kernal version.
 */
const defaultMinKernelVersion = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.DEFAULT_MIN_HWE_KERNEL)
);

/**
 * Returns the MAAS config for enabling DNSSEC validation of upstream zones.
 * @param state - The redux state.
 * @returns DNSSEC validation type.
 */
const dnssecValidation = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.DNSSEC_VALIDATION)
);

/**
 * Returns the possible DNSSEC validation options reformatted as objects.
 * @param state - The redux state.
 * @returns {Option[]} DNSSEC validation options.
 */
const dnssecOptions = createSelector([all], (configs) =>
  getOptionsFromName<string>(configs, ConfigNames.DNSSEC_VALIDATION)
);

/**
 * Returns the MAAS config for the list of external networks that will be allowed to use MAAS for DNS resolution.
 * @param state - The redux state.
 * @returns External networks.
 */
const dnsTrustedAcl = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.DNS_TRUSTED_ACL)
);

/**
 * Returns the MAAS config for upstream DNS.
 * @param state - The redux state.
 * @returns Upstream DNS(s).
 */
const upstreamDns = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.UPSTREAM_DNS)
);

/**
 * Returns the MAAS config for NTP servers.
 * @param state - The redux state.
 * @returns NTP server(s).
 */
const ntpServers = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.NTP_SERVERS)
);

/**
 * Returns the MAAS config for only enabling external NTP servers.
 * @param state - The redux state.
 * @returns Enable external NTP servers only.
 */
const ntpExternalOnly = createSelector([all], (configs) =>
  getValueFromName<boolean>(configs, ConfigNames.NTP_EXTERNAL_ONLY)
);

/**
 * Returns the MAAS config for remote syslog server to forward machine logs.
 * @param state - The redux state.
 * @returns Remote syslog server.
 */
const remoteSyslog = createSelector([all], (configs) =>
  getValueFromName<string | null>(configs, ConfigNames.REMOTE_SYSLOG)
);

/**
 * Returns the MAAS config for enabling network discovery.
 * @param state - The redux state.
 * @returns Enable network discovery.
 */
const networkDiscovery = createSelector([all], (configs) =>
  getValueFromName<NetworkDiscovery>(configs, ConfigNames.NETWORK_DISCOVERY)
);

/**
 * Returns the possible network discovery options reformatted as objects.
 * @param state - The redux state.
 * @returns {Option[]} Network discovery options.
 */
const networkDiscoveryOptions = createSelector([all], (configs) =>
  getOptionsFromName<string>(configs, ConfigNames.NETWORK_DISCOVERY)
);

/**
 * Returns the MAAS config for active discovery interval.
 * @param state - The redux state.
 * @returns Active discovery interval in ms.
 */
const activeDiscoveryInterval = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.ACTIVE_DISCOVERY_INTERVAL)
);

/**
 * Returns the possible active discovery intervals reformatted as objects.
 * @param state - The redux state.
 * @returns {Option[]} Active discovery intervals.
 */
const discoveryIntervalOptions = createSelector([all], (configs) =>
  getOptionsFromName<string>(configs, ConfigNames.ACTIVE_DISCOVERY_INTERVAL)
);

/**
 * Returns the MAAS config for kernel parameters.
 * @param state - The redux state.
 * @returns Kernel parameters.
 */
const kernelParams = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.KERNEL_OPTS)
);

/**
 * Returns the MAAS config for Windows KMS host.
 * @param state - The redux state.
 * @returns Windows KMS host.
 */
const windowsKmsHost = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.WINDOWS_KMS_HOST)
);

/**
 * Returns the MAAS config for vCenter server.
 * @param state - The redux state.
 * @returns - vCenter server.
 */
const vCenterServer = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.VCENTER_SERVER)
);

/**
 * Returns the MAAS config for vCenter username.
 * @param state - The redux state.
 * @returns - vCenter username.
 */
const vCenterUsername = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.VCENTER_USERNAME)
);

/**
 * Returns the MAAS config for vCenter password.
 * @param state - The redux state.
 * @returns - vCenter password.
 */
const vCenterPassword = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.VCENTER_PASSWORD)
);

/**
 * Returns the MAAS config for vCenter datacenter.
 * @param state - The redux state.
 * @returns - vCenter datacenter.
 */
const vCenterDatacenter = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.VCENTER_DATACENTER)
);

/**
 * Returns the MAAS config for enable_third_party_drivers
 * @param state - The redux state
 * @returns - The value of enable_third_party_drivers
 */
const thirdPartyDriversEnabled = createSelector([all], (configs) =>
  getValueFromName<boolean>(configs, ConfigNames.ENABLE_THIRD_PARTY_DRIVERS)
);

/**
 * Returns the MAAS config for default OS.
 * @param state - The redux state.
 * @returns Default OS.
 */
const defaultOSystem = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.DEFAULT_OSYSTEM)
);

/**
 * Returns the possible default OS options reformatted as objects.
 * @param state - The redux state.
 * @returns {Option[]} Default OS options.
 */
const defaultOSystemOptions = createSelector([all], (configs) =>
  getOptionsFromName<string>(configs, ConfigNames.DEFAULT_OSYSTEM)
);

/**
 * Returns the MAAS config for default distro series.
 * @param state - The redux state.
 * @returns Default distro series.
 */
const defaultDistroSeries = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.DEFAULT_DISTRO_SERIES)
);

/**
 * Returns the MAAS config for default IPMI user.
 * @param state - The redux state.
 * @returns Default IPMI user.
 */
const maasAutoIpmiUser = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.MAAS_AUTO_IPMI_USER)
);

/**
 * Returns the MAAS config for the IPMI user privilege level.
 * @param state - The redux state.
 * @returns IPMI privilege level.
 */
const maasAutoUserPrivilegeLevel = createSelector([all], (configs) =>
  getValueFromName<AutoIpmiPrivilegeLevel>(
    configs,
    ConfigNames.MAAS_AUTO_IPMI_USER_PRIVILEGE_LEVEL
  )
);

/**
 * Returns the MAAS config for the IPMI BMC key.
 * @param state - The redux state.
 * @returns BMC key.
 */
const maasAutoIpmiKGBmcKey = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.MAAS_AUTO_IPMI_K_G_BMC_KEY)
);

/**
 * Returns the MAAS url.
 * @param state - The redux state.
 * @returns MAAS url.
 */
const maasUrl = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.MAAS_URL)
);

/**
 * Returns the MAAS config for whether the intro has been completed.
 * @param state - The redux state.
 * @returns Whether the intro has been completed
 */
const completedIntro = createSelector([all], (configs) =>
  getValueFromName<boolean>(configs, ConfigNames.COMPLETED_INTRO)
);

/**
 * Returns the MAAS config for whether the release notifications are enabled.
 * @param state - The redux state.
 * @returns Whether the release notifications are enabled.
 */
const releaseNotifications = createSelector([all], (configs) =>
  getValueFromName<boolean>(configs, ConfigNames.RELEASE_NOTIFICATIONS)
);

/**
 * Returns the RPC shared secret.
 * @param state - The redux state.
 * @returns RPC shared secret.
 */
const rpcSharedSecret = createSelector([all], (configs) =>
  getValueFromName<string>(configs, ConfigNames.RPC_SHARED_SECRET)
);

const hardwareSyncInterval = createSelector([all], (configs) =>
  getValueFromName<TimeSpan>(configs, ConfigNames.HARDWARE_SYNC_INTERVAL)
);

/**
 * Returns MAAS config for whether the TLS expiration notification is enabled.
 * @param state - The redux state.
 * @returns Whether the TLS expiration notification is enabled.
 */
const tlsCertExpirationNotificationEnabled = createSelector([all], (configs) =>
  getValueFromName<boolean>(
    configs,
    ConfigNames.TLS_CERT_EXPIRATION_NOTIFICATION_ENABLED
  )
);

/**
 * Returns MAAS config for the interval in which to show TLS expiration notification.
 * @param state - The redux state.
 * @returns The interval in which to show TLS expiration notification.
 */
const tlsCertExpirationNotificationInterval = createSelector([all], (configs) =>
  getValueFromName<Days>(
    configs,
    ConfigNames.TLS_CERT_EXPIRATION_NOTIFICATION_INTERVAL
  )
);

const enableKernelCrashDump = createSelector([all], (configs) =>
  getValueFromName<boolean>(configs, ConfigNames.ENABLE_KERNEL_CRASH_DUMP)
);

const config = {
  activeDiscoveryInterval,
  all,
  analyticsEnabled,
  commissioningDistroSeries,
  completedIntro,
  defaultDistroSeries,
  defaultMinKernelVersion,
  defaultOSystem,
  defaultOSystemOptions,
  defaultStorageLayout,
  discoveryIntervalOptions,
  diskEraseWithQuick,
  diskEraseWithSecure,
  distroSeriesOptions,
  dnssecOptions,
  dnssecValidation,
  dnsTrustedAcl,
  enableDiskErasing,
  enableHttpProxy,
  enableKernelCrashDump,
  errors,
  hardwareSyncInterval,
  httpProxy,
  kernelParams,
  loaded,
  loading,
  maasName,
  maasAutoIpmiUser,
  maasAutoIpmiKGBmcKey,
  maasAutoUserPrivilegeLevel,
  maasUrl,
  networkDiscovery,
  networkDiscoveryOptions,
  ntpExternalOnly,
  ntpServers,
  proxyType,
  releaseNotifications,
  remoteSyslog,
  rpcSharedSecret,
  saved,
  saving,
  sessionLength,
  storageLayoutOptions,
  theme,
  thirdPartyDriversEnabled,
  tlsCertExpirationNotificationEnabled,
  tlsCertExpirationNotificationInterval,
  upstreamDns,
  usePeerProxy,
  uuid,
  vCenterDatacenter,
  vCenterPassword,
  vCenterServer,
  vCenterUsername,
  windowsKmsHost,
};

export default config;
