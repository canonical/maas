import { ExternalLink } from "@canonical/maas-react-components";

import FormikField from "@/app/base/components/FormikField";
import TooltipButton from "@/app/base/components/TooltipButton";
import docsUrls from "@/app/base/docsUrls";

export enum Labels {
  IPMIUsername = "MAAS generated IPMI username",
  KGBMCKeyLabel = "Auto IPMI K_g BMC key",
  UserRadio = "User",
  AdminRadio = "Admin",
  OperatorRadio = "Operator",
}

const IpmiFormFields = (): React.ReactElement => {
  return (
    <>
      <FormikField
        autoComplete="username"
        label={Labels.IPMIUsername}
        name="maas_auto_ipmi_user"
        placeholder="maas"
        type="text"
      />
      <FormikField
        aria-label={Labels.KGBMCKeyLabel}
        autoComplete="new-password"
        help={
          <>
            Specify this key to encrypt all communication between IPMI clients
            and the BMC. Leave this blank for no encryption.&nbsp;
            <ExternalLink to={docsUrls.ipmi}>IPMI and BMC key</ExternalLink>
          </>
        }
        label={
          <>
            K_g BMC key&nbsp;
            <TooltipButton
              iconName="help"
              message="Once set, the IPMI K_g BMC key is REQUIRED after next commissioning."
            />
          </>
        }
        name="maas_auto_ipmi_k_g_bmc_key"
        type="password"
      />
      <p className="u-sv1">MAAS generated IPMI user privilege level</p>
      <FormikField
        label={Labels.AdminRadio}
        name="maas_auto_ipmi_user_privilege_level"
        type="radio"
        value="ADMIN"
      />
      <FormikField
        label={Labels.OperatorRadio}
        name="maas_auto_ipmi_user_privilege_level"
        type="radio"
        value="OPERATOR"
      />
      <FormikField
        label={Labels.UserRadio}
        name="maas_auto_ipmi_user_privilege_level"
        type="radio"
        value="USER"
      />
    </>
  );
};

export default IpmiFormFields;
