import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import type { DHCPFormValues } from "./types";

import DhcpFormFields from "@/app/base/components/DhcpFormFields";
import FormikForm from "@/app/base/components/FormikForm";
import type { Props as FormikFormProps } from "@/app/base/components/FormikForm/FormikForm";
import { useFetchActions } from "@/app/base/hooks";
import { useDhcpTarget } from "@/app/settings/hooks";
import { controllerActions } from "@/app/store/controller";
import { deviceActions } from "@/app/store/device";
import { dhcpsnippetActions } from "@/app/store/dhcpsnippet";
import dhcpsnippetSelectors from "@/app/store/dhcpsnippet/selectors";
import type { DHCPSnippet } from "@/app/store/dhcpsnippet/types";
import { ipRangeActions } from "@/app/store/iprange";
import ipRangeSelectors from "@/app/store/iprange/selectors";
import { useFetchMachines } from "@/app/store/machine/utils/hooks";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";

const DhcpSchema = Yup.object()
  .shape({
    description: Yup.string(),
    enabled: Yup.boolean(),
    entity: Yup.string().when("type", {
      is: (val: string) => val && val.length > 0,
      then: Yup.string().required(
        "You must choose an entity for this snippet type"
      ),
    }),
    name: Yup.string().required("Snippet name is required"),
    value: Yup.string().required("DHCP snippet is required"),
    type: Yup.string(),
  })
  .defined();

type Props = Partial<FormikFormProps<DHCPFormValues>> & {
  analyticsCategory: string;
  id?: DHCPSnippet["id"];
  onSave?: () => void;
};

export enum Labels {
  Form = "DHCP Form",
  LoadingData = "Loading DHCP snippet data",
  Submit = "Save snippet",
}

export const DhcpForm = ({
  analyticsCategory,
  id,
  onSave,
  ...props
}: Props): React.ReactElement => {
  const dispatch = useDispatch();
  const dhcpSnippet = useSelector((state: RootState) =>
    dhcpsnippetSelectors.getById(state, id)
  );
  const errors = useSelector(dhcpsnippetSelectors.errors);
  const saved = useSelector(dhcpsnippetSelectors.saved);
  const saving = useSelector(dhcpsnippetSelectors.saving);
  const editing = !!dhcpSnippet;
  const ipRanges = useSelector(ipRangeSelectors.all);
  const {
    loading,
    loaded,
    type: targetType,
  } = useDhcpTarget(
    editing ? dhcpSnippet?.node : null,
    editing ? dhcpSnippet?.subnet : null,
    editing ? dhcpSnippet?.iprange : null
  );
  useFetchMachines();

  useFetchActions([
    subnetActions.fetch,
    controllerActions.fetch,
    deviceActions.fetch,
    ipRangeActions.fetch,
  ]);

  if (
    editing &&
    (dhcpSnippet?.node || dhcpSnippet?.subnet) &&
    (loading || !loaded)
  ) {
    return <Spinner aria-label={Labels.LoadingData} text="Loading..." />;
  }

  return (
    <FormikForm<DHCPFormValues>
      aria-label={Labels.Form}
      cleanup={dhcpsnippetActions.cleanup}
      errors={errors}
      initialValues={{
        description: dhcpSnippet ? dhcpSnippet.description : "",
        enabled: dhcpSnippet ? dhcpSnippet.enabled : false,
        entity: dhcpSnippet
          ? dhcpSnippet.node ||
            `${dhcpSnippet.iprange || dhcpSnippet.subnet}` ||
            ""
          : "",
        name: dhcpSnippet ? dhcpSnippet.name : "",
        type: (dhcpSnippet && targetType) || "",
        value: dhcpSnippet ? dhcpSnippet.value : "",
      }}
      onSaveAnalytics={{
        action: "Saved",
        category: analyticsCategory,
        label: `${editing ? "Edit" : "Add"} form`,
      }}
      onSubmit={(values) => {
        const params: {
          description: DHCPFormValues["description"];
          enabled: DHCPFormValues["enabled"];
          name: DHCPFormValues["name"];
          node?: DHCPSnippet["node"];
          iprange?: DHCPSnippet["iprange"];
          subnet?: DHCPSnippet["subnet"];
          value: DHCPFormValues["value"];
        } = {
          description: values.description,
          enabled: values.enabled,
          name: values.name,
          value: values.value,
        };
        if (values.type === "iprange") {
          params.iprange = parseInt(values.entity, 10);
          params.subnet = ipRanges.filter(
            (iprange) => iprange.id === params.iprange
          )[0]?.subnet;
        } else if (values.type === "subnet") {
          params.subnet = parseInt(values.entity, 10);
        } else if (values.type) {
          params.node = values.entity;
        }
        if (editing) {
          if (dhcpSnippet) {
            dispatch(
              dhcpsnippetActions.update({
                id: dhcpSnippet.id,
                ...params,
              })
            );
          }
        } else {
          dispatch(dhcpsnippetActions.create(params));
        }
      }}
      onSuccess={() => {
        if (onSave) {
          onSave();
        }
      }}
      saved={saved}
      saving={saving}
      submitLabel={Labels.Submit}
      validationSchema={DhcpSchema}
      {...props}
    >
      <DhcpFormFields editing={editing} />
    </FormikForm>
  );
};

export default DhcpForm;
