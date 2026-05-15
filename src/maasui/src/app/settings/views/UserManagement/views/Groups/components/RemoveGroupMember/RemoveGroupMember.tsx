import type { Dispatch, SetStateAction } from "react";

import pluralize from "pluralize";

import { useRemoveGroupMembers } from "@/app/api/query/groups";
import type {
  UserGroupMemberResponse,
  UserGroupResponse,
} from "@/app/apiclient";
import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";

type RemoveGroupMemberProps = {
  groupId: UserGroupResponse["id"];
  members: UserGroupMemberResponse[];
  setMemberSelection: Dispatch<SetStateAction<UserGroupMemberResponse[]>>;
};

const RemoveGroupMember = ({
  groupId,
  members,
  setMemberSelection,
}: RemoveGroupMemberProps) => {
  const { closeSidePanel } = useSidePanel();
  const removeMembers = useRemoveGroupMembers();

  return (
    <ModelActionForm
      aria-label="Remove group member"
      errors={removeMembers.error}
      initialValues={{}}
      message={
        <>
          <p>
            Are you sure you want to remove the following{" "}
            {pluralize("member", members.length)} from the group?
          </p>
          <ul>
            {members.map(({ username, email }) => (
              <li key={username}>
                {username} ({email})
              </li>
            ))}
          </ul>
        </>
      }
      modelType="group member"
      onCancel={closeSidePanel}
      onSubmit={() => {
        removeMembers.mutate({
          path: {
            group_id: groupId,
          },
          query: {
            id: members.map((member) => member.user_id),
          },
        });
      }}
      onSuccess={() => {
        setMemberSelection((prev) =>
          prev.filter((m) => !members.some((r) => r.user_id === m.user_id))
        );
        closeSidePanel();
      }}
      saved={removeMembers.isSuccess}
      saving={removeMembers.isPending}
      submitAppearance="negative"
      submitLabel={`Remove ${members.length} ${pluralize("member", members.length)}`}
    />
  );
};

export default RemoveGroupMember;
