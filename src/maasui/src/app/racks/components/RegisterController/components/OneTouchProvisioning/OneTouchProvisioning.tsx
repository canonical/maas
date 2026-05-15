import type { ReactElement } from "react";

import { ExternalLink } from "@canonical/maas-react-components";
import { FormikField } from "@canonical/react-components";
import * as Yup from "yup";

import FormikForm from "@/app/base/components/FormikForm";
import docsUrls from "@/app/base/docsUrls";
import { useSidePanel } from "@/app/base/side-panel-context";

//TODO when endpoint is ready
export type OneTouchProvisioning = {
  MAASagentsecret: string;
};

//TODO when endpoint is ready
const OneTouchProvisioningSchema = Yup.object().shape({
  name: Yup.string().required("'MAAS Agent secret' is a required field."),
});

const OneTouchProvisioning = (): ReactElement => {
  const { closeSidePanel } = useSidePanel();
  //TODO when endpoint is ready
  return (
    <div>
      To register a controller to the rack using one-touch provisioning,
      physically retrieve the MAAS agent secret of the controller from the
      hardware.
      <FormikForm<OneTouchProvisioning, string>
        aria-label="One-touch provisioning"
        buttonsHelp={
          <p>
            <ExternalLink to={docsUrls.rackController}>
              Help with registering controllers
            </ExternalLink>
          </p>
        }
        buttonsHelpClassName="u-align--right"
        initialValues={{
          MAASagentsecret: "",
        }}
        onCancel={closeSidePanel}
        onSubmit={() => {}}
        onSuccess={() => {
          closeSidePanel();
        }}
        resetOnSave={true}
        submitLabel="Register controller"
        // saved={registerController.isSuccess}
        // saving={registerController.isPending}
        validationSchema={OneTouchProvisioningSchema}
        // errors={registerController.error}
      >
        <FormikField
          label="* MAAS agent secret"
          name="* MAAS agent secret"
          type="text"
        />
      </FormikForm>
    </div>
  );
};

export default OneTouchProvisioning;
