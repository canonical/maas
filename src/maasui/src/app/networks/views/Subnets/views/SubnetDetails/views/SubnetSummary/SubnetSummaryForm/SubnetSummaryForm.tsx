import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import SubnetSummaryFormFields from "./SubnetSummaryFormFields";
import type { SubnetSummaryFormValues } from "./types";

import FormikForm from "@/app/base/components/FormikForm";
import { useFetchActions } from "@/app/base/hooks";
import { fabricActions } from "@/app/store/fabric";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet, SubnetMeta } from "@/app/store/subnet/types";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";

const subnetSummaryFormSchema = Yup.object().shape({
  name: Yup.string(),
  cidr: Yup.string(),
  gateway_ip: Yup.string(),
  dns_servers: Yup.string(),
  description: Yup.string(),
  managed: Yup.boolean(),
  active_discovery: Yup.boolean(),
  allow_proxy: Yup.boolean(),
  allow_dns: Yup.boolean(),
  vlan: Yup.number().required("VLAN is required"),
});

type Props = {
  handleDismiss: () => void;
  id: Subnet[SubnetMeta.PK];
};

const SubnetSummaryForm = ({
  handleDismiss,
  id,
}: Props): React.ReactElement | null => {
  const dispatch = useDispatch();
  const subnetErrors = useSelector(subnetSelectors.errors);
  const saving = useSelector(subnetSelectors.saving);
  const saved = useSelector(subnetSelectors.saved);
  const subnet = useSelector((state: RootState) =>
    subnetSelectors.getById(state, id)
  );
  const vlan = useSelector((state: RootState) =>
    vlanSelectors.getById(state, subnet?.vlan)
  );

  useFetchActions([fabricActions.fetch, vlanActions.fetch]);

  if (!subnet || !vlan) {
    return null;
  }

  return (
    <FormikForm<SubnetSummaryFormValues>
      aria-label="Edit subnet"
      cleanup={subnetActions.cleanup}
      errors={subnetErrors}
      initialValues={{
        active_discovery: subnet.active_discovery,
        allow_dns: subnet.allow_dns,
        allow_proxy: subnet.allow_proxy,
        cidr: subnet.cidr,
        description: subnet.description,
        dns_servers: subnet.dns_servers,
        fabric: vlan.fabric.toString(),
        gateway_ip: subnet.gateway_ip || "",
        managed: subnet.managed,
        name: subnet.name,
        vlan: subnet.vlan.toString(),
      }}
      onCancel={handleDismiss}
      onSaveAnalytics={{
        action: "Save",
        category: "Subnet",
        label: "Subnet summary form",
      }}
      onSubmit={(values) => {
        dispatch(subnetActions.cleanup());
        dispatch(
          subnetActions.update({
            active_discovery: values.active_discovery,
            allow_dns: values.allow_dns,
            allow_proxy: values.allow_proxy,
            cidr: values.cidr,
            description: values.description,
            dns_servers: values.dns_servers,
            gateway_ip: values.gateway_ip,
            id: subnet.id,
            managed: values.managed,
            name: values.name,
            vlan: Number(values.vlan),
          })
        );
      }}
      onSuccess={() => {
        handleDismiss();
      }}
      resetOnSave
      saved={saved}
      saving={saving}
      submitLabel="Save"
      validationSchema={subnetSummaryFormSchema}
    >
      <SubnetSummaryFormFields />
    </FormikForm>
  );
};

export default SubnetSummaryForm;
