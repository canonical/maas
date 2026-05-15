import { ExternalLink } from "@canonical/maas-react-components";
import {
  Icon,
  Spinner,
  CodeSnippet,
  CodeSnippetBlockAppearance,
} from "@canonical/react-components";
import { useSelector } from "react-redux";

import docsUrls from "@/app/base/docsUrls";
import { useFetchActions } from "@/app/base/hooks";
import { useId } from "@/app/base/hooks/base";
import { controllerActions } from "@/app/store/controller";
import controllerSelectors from "@/app/store/controller/selectors";
import { generalActions } from "@/app/store/general";
import { vaultEnabled as vaultEnabledSelectors } from "@/app/store/general/selectors";
import type { RootState } from "@/app/store/root/types";

export enum Labels {
  Loading = "Loading...",
  IntegrateWithVault = "Integrate with Vault",
  VaultEnabled = "Vault enabled",
  SetupInstructions = "Vault setup instructions",
  SecretMigrationInstructions = "Incomplete Vault integration, migrate secrets on one region controller to complete setup.",
}

const VaultSettings = (): React.ReactElement => {
  const controllersLoading = useSelector(controllerSelectors.loading);
  const vaultEnabledLoading = useSelector(vaultEnabledSelectors.loading);
  const vaultEnabled = useSelector((state: RootState) =>
    vaultEnabledSelectors.get(state)
  );
  const id = useId();

  const { unconfiguredControllers, configuredControllers } = useSelector(
    (state: RootState) =>
      controllerSelectors.getVaultConfiguredControllers(state)
  );

  useFetchActions([controllerActions.fetch, generalActions.fetchVaultEnabled]);

  if (controllersLoading || vaultEnabledLoading)
    return <Spinner aria-label={Labels.Loading} text={Labels.Loading} />;

  if (vaultEnabled) {
    return (
      <>
        <p>
          <Icon name="security-tick" />
          <span className="u-nudge-right--small">Vault enabled</span>
        </p>
        <a href={docsUrls.aboutNativeTLS}>More about Vault integration</a>
      </>
    );
  } else
    return (
      <>
        {unconfiguredControllers.length >= 1 ? (
          <>
            {configuredControllers.length >= 1 ? (
              <p>
                <Icon name="security-warning" />
                <span className="u-nudge-right--small" id={id}>
                  Incomplete Vault integration, configure{" "}
                  {unconfiguredControllers.length} other{" "}
                  {unconfiguredControllers.length > 1
                    ? "controllers"
                    : "controller"}{" "}
                  with Vault to complete this operation.
                </span>
              </p>
            ) : (
              <h5>
                <Icon name="security" />
                <span className="u-nudge-right--small" id={id}>
                  {Labels.IntegrateWithVault}
                </span>
              </h5>
            )}
            <section aria-labelledby={id}>
              <p>
                1. Get the $wrapped_token and $role_id from Vault.{" "}
                <ExternalLink to="https://learn.hashicorp.com/tutorials/vault/approle-best-practices?in=vault/auth-methods#approle-response-wrapping">
                  Find out more from Hashicorp Vault
                </ExternalLink>
                .
              </p>
              <p>2. SSH into each region controller and configure Vault.</p>
              <CodeSnippet
                blocks={[
                  {
                    appearance: CodeSnippetBlockAppearance.LINUX_PROMPT,
                    code: "sudo maas config-vault configure $url $approle_id $wrapped_token $secrets_path --secrets-mount $secret_mount",
                  },
                ]}
              />
              <p>
                3. After Vault is configured on all region controllers, migrate
                secrets on one of the region controllers.
              </p>
              <CodeSnippet
                blocks={[
                  {
                    appearance: CodeSnippetBlockAppearance.LINUX_PROMPT,
                    code: "sudo maas config-vault migrate",
                  },
                ]}
              />
            </section>
          </>
        ) : (
          <>
            <p>
              <Icon name="security-warning" />
              <span className="u-nudge-right--small" id={id}>
                {Labels.SecretMigrationInstructions}
              </span>
            </p>
            <section aria-labelledby={id}>
              <CodeSnippet
                blocks={[
                  {
                    appearance: CodeSnippetBlockAppearance.LINUX_PROMPT,
                    code: "sudo maas config-vault migrate",
                  },
                ]}
              />
            </section>
          </>
        )}
        <a href={docsUrls.vaultIntegration}>More about Vault integration</a>
      </>
    );
};

export default VaultSettings;
