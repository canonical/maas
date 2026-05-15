import { useState } from "react";

import { Card, Icon } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import { useNavigate } from "react-router";
import * as Yup from "yup";

import ConnectivityCard from "./ConnectivityCard";
import NameCard from "./NameCard";
import type { MaasIntroValues } from "./types";

import { useGetCurrentUser } from "@/app/api/query/auth";
import FormikForm from "@/app/base/components/FormikForm";
import TableConfirm from "@/app/base/components/TableConfirm";
import { useFetchActions } from "@/app/base/hooks";
import type { SyncNavigateFunction } from "@/app/base/types";
import urls from "@/app/base/urls";
import { UrlSchema } from "@/app/base/validation";
import IntroSection from "@/app/intro/components/IntroSection";
import { useExitURL } from "@/app/intro/hooks";
import { configActions } from "@/app/store/config";
import configSelectors from "@/app/store/config/selectors";
import { repositoryActions } from "@/app/store/packagerepository";
import repoSelectors from "@/app/store/packagerepository/selectors";
import { setCookie } from "@/app/utils";

export enum Labels {
  SecondarySubmit = "Skip setup",
  SubmitLabel = "Save and continue",
  AreYouSure = "Are you sure you want to skip the initial MAAS setup? You will still be able to find all configuration options in the Settings and Images tabs.",
  SkipToUserSetup = "Skip to user setup",
}

export const MaasIntroSchema = Yup.object()
  .shape({
    httpProxy: UrlSchema,
    mainArchiveUrl: UrlSchema.required("Ubuntu archive is required."),
    name: Yup.string().required("MAAS name is required"),
    portsArchiveUrl: UrlSchema.required(
      "Ubuntu extra architectures is required."
    ),
    upstreamDns: Yup.string(),
  })
  .defined();

const MaasIntro = (): React.ReactElement => {
  const dispatch = useDispatch();
  const navigate: SyncNavigateFunction = useNavigate();
  const httpProxy = useSelector(configSelectors.httpProxy);
  const maasName = useSelector(configSelectors.maasName);
  const upstreamDns = useSelector(configSelectors.upstreamDns);
  const configErrors = useSelector(configSelectors.errors);
  const configLoading = useSelector(configSelectors.loading);
  const configSaved = useSelector(configSelectors.saved);
  const configSaving = useSelector(configSelectors.saving);
  const reposErrors = useSelector(repoSelectors.errors);
  const reposLoading = useSelector(repoSelectors.loading);
  const reposSaving = useSelector(repoSelectors.saving);
  const mainArchive = useSelector(repoSelectors.mainArchive);
  const portsArchive = useSelector(repoSelectors.portsArchive);
  const [showSkip, setShowSkip] = useState(false);
  const exitURL = useExitURL();

  const user = useGetCurrentUser();

  useFetchActions([repositoryActions.fetch]);

  const errors = {
    ...(configErrors && typeof configErrors === "object" ? configErrors : {}),
    ...(reposErrors && typeof reposErrors === "object" ? reposErrors : {}),
  };
  const loading = user.isPending || configLoading || reposLoading;
  const saving = configSaving || reposSaving;
  return (
    <IntroSection loading={loading}>
      <>
        <FormikForm<MaasIntroValues>
          allowUnchanged
          cleanup={configActions.cleanup}
          editable={!showSkip}
          errors={errors}
          initialValues={{
            httpProxy: httpProxy || "",
            mainArchiveUrl: mainArchive?.url || "",
            name: maasName || "",
            portsArchiveUrl: portsArchive?.url || "",
            upstreamDns: upstreamDns || "",
          }}
          onSaveAnalytics={{
            action: "Saved",
            category: "Intro",
            label: "Intro form",
          }}
          onSubmit={(values) => {
            dispatch(configActions.cleanup());
            dispatch(repositoryActions.cleanup());
            dispatch(
              configActions.update({
                http_proxy: values.httpProxy,
                maas_name: values.name,
                upstream_dns: values.upstreamDns,
              })
            );
            if (mainArchive && mainArchive.url !== values.mainArchiveUrl) {
              dispatch(
                repositoryActions.update({
                  id: mainArchive.id,
                  name: mainArchive.name,
                  url: values.mainArchiveUrl,
                })
              );
            }
            if (portsArchive && portsArchive.url !== values.portsArchiveUrl) {
              dispatch(
                repositoryActions.update({
                  id: portsArchive.id,
                  name: portsArchive.name,
                  url: values.portsArchiveUrl,
                })
              );
            }
          }}
          saved={configSaved}
          savedRedirect={urls.intro.images}
          saving={saving}
          secondarySubmit={() => {
            setShowSkip(true);
          }}
          secondarySubmitLabel={Labels.SecondarySubmit}
          submitLabel={Labels.SubmitLabel}
          validationSchema={MaasIntroSchema}
        >
          <NameCard />
          <ConnectivityCard />
        </FormikForm>
        {showSkip && (
          <Card data-testid="skip-setup" highlighted>
            <TableConfirm
              confirmLabel={
                user.data?.statistics?.completed_intro
                  ? Labels.SecondarySubmit
                  : Labels.SkipToUserSetup
              }
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
                dispatch(configActions.update({ completed_intro: true }));
                setCookie("skipsetupintro", "true");
                if (!user.data?.statistics?.completed_intro) {
                  navigate({ pathname: urls.intro.user });
                } else {
                  navigate({
                    pathname: exitURL,
                  });
                }
              }}
              sidebar={false}
            />
          </Card>
        )}
      </>
    </IntroSection>
  );
};

export default MaasIntro;
