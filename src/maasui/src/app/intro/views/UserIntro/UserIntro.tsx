import { useState } from "react";

import { ActionButton, Button, Card, Icon } from "@canonical/react-components";

import { useCompleteIntro, useGetCurrentUser } from "@/app/api/query/auth";
import { useListSshKeys } from "@/app/api/query/sshKeys";
import TableConfirm from "@/app/base/components/TableConfirm";
import { useCycled } from "@/app/base/hooks";
import IntroCard from "@/app/intro/components/IntroCard";
import IntroSection from "@/app/intro/components/IntroSection";
import { AddSSHKey } from "@/app/preferences/views/SSHKeys/components";
import SSHKeysList from "@/app/preferences/views/SSHKeys/views";
import { formatErrors, setCookie } from "@/app/utils";

export enum Labels {
  Continue = "Finish setup",
  Skip = "Skip user setup",
  AreYouSure = "Are you sure you want to skip your user setup? You will still be able to manage your SSH keys in your user preferences.",
}

const UserIntro = (): React.ReactElement => {
  const [showSkip, setShowSkip] = useState(false);

  const user = useGetCurrentUser();
  const eTag = user.data?.headers?.get("ETag");
  const completeIntro = useCompleteIntro();
  const { data, isPending: sshKeyLoading } = useListSshKeys();
  const [markedIntroComplete] = useCycled(completeIntro.isPending);

  const sshkeys = data?.items || [];
  const hasSSHKeys = sshkeys.length > 0;
  const errorMessage = formatErrors(
    user.isError ? user.error?.message : undefined
  );

  return (
    <IntroSection
      errors={errorMessage}
      loading={user.isPending || sshKeyLoading}
      shouldExitIntro={
        user.data?.statistics?.completed_intro ||
        (completeIntro.isSuccess && markedIntroComplete)
      }
      windowTitle="User"
    >
      <IntroCard
        complete={hasSSHKeys}
        data-testid="sshkey-card"
        hasErrors={!!errorMessage}
        title={`SSH keys for ${user.data?.username}`}
      >
        <p>
          Add multiple keys from Launchpad and Github or enter them manually.
        </p>
        <h4>Keys</h4>
        {hasSSHKeys ? <SSHKeysList isIntro={true} /> : null}
        <AddSSHKey isIntro={true} />
      </IntroCard>
      <div className="u-align--right">
        <Button
          data-testid="skip-button"
          onClick={() => {
            setShowSkip(true);
          }}
        >
          {Labels.Skip}
        </Button>
        <ActionButton
          appearance="positive"
          data-testid="continue-button"
          disabled={!hasSSHKeys}
          loading={completeIntro.isPending && !showSkip}
          onClick={() => {
            completeIntro.mutate({
              headers: {
                ETag: eTag,
              },
            });
          }}
          success={completeIntro.isSuccess}
        >
          {Labels.Continue}
        </ActionButton>
      </div>
      {showSkip && (
        <Card data-testid="skip-setup" highlighted>
          <TableConfirm
            confirmLabel={Labels.Skip}
            errors={completeIntro.error?.message}
            finished={completeIntro.isSuccess}
            inProgress={completeIntro.isPending && showSkip}
            message={
              <>
                <Icon className="is-inline" name="warning" />
                {Labels.AreYouSure}
              </>
            }
            onClose={() => {
              setShowSkip(false);
            }}
            onConfirm={() => {
              setCookie("skipintro", "true");
              completeIntro.mutate({});
            }}
            sidebar={false}
          />
        </Card>
      )}
    </IntroSection>
  );
};

export default UserIntro;
