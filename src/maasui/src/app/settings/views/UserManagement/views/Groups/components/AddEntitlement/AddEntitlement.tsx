import type { ChangeEvent } from "react";

import { Icon, Select, Tooltip } from "@canonical/react-components";
import type { FormikContextType } from "formik";
import * as Yup from "yup";

import { Entitlement, RestrictableEntitlements } from "../../constants";

import { useAddGroupEntitlement } from "@/app/api/query/groups";
import { usePools } from "@/app/api/query/pools";
import type {
  AddGroupEntitlementError,
  UserGroupResponse,
} from "@/app/apiclient";
import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";

type AddEntitlementValues = {
  entitlement: string;
  is_restricted: boolean;
  pool_id: string;
};

type AddEntitlementProps = {
  group_id: UserGroupResponse["id"];
};

const AddEntitlementSchema = Yup.object().shape({
  entitlement: Yup.string().required("Entitlement is required."),
  is_restricted: Yup.boolean(),
  pool_id: Yup.string().when("is_restricted", {
    is: true,
    then: (schema) => schema.required("Pool is required."),
    otherwise: (schema) => schema,
  }),
});

const AddEntitlement = ({ group_id }: AddEntitlementProps) => {
  const { closeSidePanel } = useSidePanel();
  const pools = usePools();
  const addEntitlement = useAddGroupEntitlement();

  const entitlementOptions = [
    { label: "Select entitlement", value: "", disabled: true },
    ...Object.values(Entitlement).map((value) => ({
      label: value,
      value,
    })),
  ];

  const poolOptions = [
    { label: "Select pool", value: "", disabled: true },
    ...(pools.data?.items ?? []).map((pool) => ({
      label: pool.name,
      value: String(pool.id),
    })),
  ];

  return (
    <FormikForm<AddEntitlementValues, AddGroupEntitlementError>
      aria-label="Add group entitlement"
      errors={addEntitlement.error}
      initialValues={{
        entitlement: "",
        is_restricted: false,
        pool_id: "",
      }}
      onCancel={closeSidePanel}
      onSubmit={(values) => {
        addEntitlement.mutate({
          body: {
            entitlement: values.entitlement,
            resource_type: values.is_restricted ? "pool" : "maas",
            resource_id: values.is_restricted ? Number(values.pool_id) : 0,
          },
          path: { group_id },
        });
      }}
      onSuccess={closeSidePanel}
      resetOnSave
      saved={addEntitlement.isSuccess}
      saving={addEntitlement.isPending}
      submitLabel="Add entitlement"
      validationSchema={AddEntitlementSchema}
    >
      {({ values, setFieldValue }: FormikContextType<AddEntitlementValues>) => {
        const isRestrictable = RestrictableEntitlements.includes(
          values.entitlement as Entitlement
        );

        return (
          <>
            <FormikField
              component={Select}
              label="Entitlement"
              name="entitlement"
              onChange={(e: ChangeEvent<HTMLSelectElement>) => {
                const newEntitlement = e.target.value;
                void setFieldValue("entitlement", newEntitlement);
                if (
                  !RestrictableEntitlements.includes(
                    newEntitlement as Entitlement
                  )
                ) {
                  void setFieldValue("is_restricted", false);
                }
              }}
              options={entitlementOptions}
              required
            />
            <FormikField
              disabled={!isRestrictable}
              help="Limits entitlement to a specific pool. If unchecked, the entitlement applies to the entire MAAS instance."
              label={
                <>
                  Restrict to pool
                  {values.entitlement && !isRestrictable && (
                    <Tooltip
                      className="u-nudge-right--small"
                      message="The selected entitlement cannot be restricted."
                    >
                      <div className="u-nudge-right--x-large">
                        <Icon name="help" />
                      </div>
                    </Tooltip>
                  )}
                </>
              }
              name="is_restricted"
              type="checkbox"
            />
            {values.is_restricted && (
              <FormikField
                component={Select}
                disabled={!pools.isSuccess}
                label="Pool"
                name="pool_id"
                options={poolOptions}
                required
              />
            )}
          </>
        );
      }}
    </FormikForm>
  );
};

export default AddEntitlement;
