import { Notification as NotificationBanner } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import controllerSelectors from "@/app/store/controller/selectors";
import { vaultEnabled as vaultEnabledSelectors } from "@/app/store/general/selectors";
import type { RootState } from "@/app/store/root/types";

const VaultNotification = (): React.ReactElement | null => {
  const { unconfiguredControllers, configuredControllers } = useSelector(
    (state: RootState) =>
      controllerSelectors.getVaultConfiguredControllers(state)
  );
  const vaultEnabled = useSelector(vaultEnabledSelectors.get);
  const vaultEnabledLoaded = useSelector(vaultEnabledSelectors.loaded);
  const controllersLoaded = useSelector(controllerSelectors.loaded);

  if (vaultEnabled || !vaultEnabledLoaded || !controllersLoaded) {
    return null;
  }

  return configuredControllers.length >= 1 &&
    unconfiguredControllers.length >= 1 ? (
    <NotificationBanner
      data-testid="vault-notification"
      severity="caution"
      title="Incomplete Vault integration"
    >
      Configure {unconfiguredControllers.length} other{" "}
      <Link to="/controllers">
        {unconfiguredControllers.length > 1 ? "controllers" : "controller"}
      </Link>{" "}
      with Vault to complete integration with Vault. Check the{" "}
      <Link to="/settings/configuration/security">security settings</Link> for
      more information.
    </NotificationBanner>
  ) : unconfiguredControllers.length === 0 &&
    configuredControllers.length >= 1 ? (
    <NotificationBanner
      data-testid="vault-notification"
      severity="caution"
      title="Incomplete Vault integration"
    >
      Migrate your secrets to Vault to complete integration with Vault. Check
      the <Link to="/settings/configuration/security">security settings</Link>{" "}
      for more information.
    </NotificationBanner>
  ) : null;
};

export default VaultNotification;
