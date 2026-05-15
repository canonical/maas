import type { ReactElement } from "react";
import { useCallback } from "react";

import { Spinner, Strip } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import type { SchemaOf } from "yup";
import * as Yup from "yup";

import AddVirshFields from "./AddVirshFields";

import { usePools } from "@/app/api/query/pools";
import { useZones } from "@/app/api/query/zones";
import FormikForm from "@/app/base/components/FormikForm";
import { useFetchActions } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import { generalActions } from "@/app/store/general";
import { powerTypes as powerTypesSelectors } from "@/app/store/general/selectors";
import { PowerFieldScope } from "@/app/store/general/types";
import {
  formatPowerParameters,
  generatePowerParametersSchema,
  useInitialPowerParameters,
} from "@/app/store/general/utils";
import { podActions } from "@/app/store/pod";
import { PodType } from "@/app/store/pod/constants";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod } from "@/app/store/pod/types";
import type { PowerParameters } from "@/app/store/types/node";

export type AddVirshValues = {
  name: string;
  pool: number | string;
  power_parameters: PowerParameters;
  type: Pod["type"];
  zone: number | string;
};

export const AddVirsh = (): ReactElement => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();

  const podSaved = useSelector(podSelectors.saved);
  const podSaving = useSelector(podSelectors.saving);
  const podErrors = useSelector(podSelectors.errors);
  const powerTypes = useSelector(powerTypesSelectors.get);
  const powerTypesLoaded = useSelector(powerTypesSelectors.loaded);
  const resourcePools = usePools();
  const zones = useZones();
  const cleanup = useCallback(() => podActions.cleanup(), []);
  const initialPowerParameters = useInitialPowerParameters();
  const loaded =
    powerTypesLoaded && !resourcePools.isPending && !zones.isPending;

  useFetchActions([generalActions.fetchPowerTypes]);

  const virshPowerType = powerTypes.find(
    (powerType) => powerType.name === PodType.VIRSH
  );

  if (!loaded) {
    return (
      <Strip shallow>
        <Spinner className="u-no-margin u-no-padding" text="Loading" />
      </Strip>
    );
  }

  const powerParametersSchema = generatePowerParametersSchema(
    virshPowerType || null,
    [PowerFieldScope.BMC]
  );
  const AddVirshSchema: SchemaOf<AddVirshValues> = Yup.object()
    .shape({
      name: Yup.string(),
      pool: Yup.string().required("Resource pool required"),
      power_parameters: Yup.object().shape(powerParametersSchema),
      type: Yup.string().required("KVM host type required"),
      zone: Yup.string().required("Zone required"),
    })
    .defined();

  return (
    <FormikForm<AddVirshValues>
      cleanup={cleanup}
      errors={podErrors}
      initialValues={{
        name: "",
        pool: resourcePools.data?.items.length
          ? resourcePools.data.items[0].id
          : "",
        power_parameters: initialPowerParameters,
        type: PodType.VIRSH,
        zone: zones.data?.items?.length ? zones.data.items[0].id : "",
      }}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Save virsh KVM",
        category: "Add KVM form",
        label: "Save KVM",
      }}
      onSubmit={(values) => {
        if (virshPowerType) {
          const params = {
            name: values.name,
            pool: Number(values.pool),
            type: values.type,
            zone: Number(values.zone),
            ...formatPowerParameters(virshPowerType, values.power_parameters, [
              PowerFieldScope.BMC,
            ]),
          };
          dispatch(podActions.create(params));
        }
      }}
      saved={podSaved}
      saving={podSaving}
      submitDisabled={!virshPowerType}
      submitLabel="Save Virsh host"
      validationSchema={AddVirshSchema}
    >
      {virshPowerType ? (
        <AddVirshFields />
      ) : (
        <Strip data-testid="virsh-unsupported" shallow>
          Virsh is not supported on this MAAS.
        </Strip>
      )}
    </FormikForm>
  );
};

export default AddVirsh;
