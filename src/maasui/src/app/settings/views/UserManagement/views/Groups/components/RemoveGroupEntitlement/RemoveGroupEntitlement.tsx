import type { Dispatch, SetStateAction } from "react";

import pluralize from "pluralize";

import { useRemoveGroupEntitlements } from "@/app/api/query/groups";
import type {
  BulkEntitlementDeleteItem,
  EntitlementResponse,
  UserGroupResponse,
} from "@/app/apiclient";
import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";

type RemoveGroupEntitlementProps = {
  group_id: UserGroupResponse["id"];
  entitlements: EntitlementResponse[];
  setEntitlementSelection: Dispatch<SetStateAction<EntitlementResponse[]>>;
};

const RemoveGroupEntitlement = ({
  group_id,
  entitlements,
  setEntitlementSelection,
}: RemoveGroupEntitlementProps) => {
  const { closeSidePanel } = useSidePanel();
  const removeEntitlements = useRemoveGroupEntitlements();

  return (
    <ModelActionForm
      aria-label="Remove group entitlement"
      errors={removeEntitlements.error}
      initialValues={{}}
      message={
        <>
          <p>
            Are you sure you want to remove the following{" "}
            {pluralize("entitlement", entitlements.length)} from the group?
          </p>
          <ul>
            {entitlements.map(({ entitlement, resource_id, resource_type }) => (
              <li key={`${entitlement}-${resource_id}`}>
                {entitlement} ({resource_type}
                {resource_id !== 0 ? `: ${resource_id}` : ""})
              </li>
            ))}
          </ul>
        </>
      }
      modelType="group entitlement"
      onCancel={closeSidePanel}
      onSubmit={() => {
        removeEntitlements.mutate({
          path: { group_id },
          body: {
            items: entitlements as BulkEntitlementDeleteItem[],
          },
        });
      }}
      onSuccess={() => {
        setEntitlementSelection((prev) =>
          prev.filter(
            (e) =>
              !entitlements.some(
                (r) =>
                  r.entitlement === e.entitlement &&
                  r.resource_id === e.resource_id
              )
          )
        );
        closeSidePanel();
      }}
      saved={removeEntitlements.isSuccess}
      saving={removeEntitlements.isPending}
      submitAppearance="negative"
      submitLabel={`Remove ${entitlements.length} ${pluralize("entitlement", entitlements.length)}`}
    />
  );
};

export default RemoveGroupEntitlement;
