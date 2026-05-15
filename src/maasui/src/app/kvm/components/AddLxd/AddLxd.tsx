import type { ReactElement } from "react";
import { useEffect, useState } from "react";

import { Stepper } from "@canonical/maas-react-components";
import { Notification as NotificationBanner } from "@canonical/react-components";
import { useDispatch } from "react-redux";

import AuthenticationForm from "./AuthenticationForm";
import CredentialsForm from "./CredentialsForm";
import SelectProjectForm from "./SelectProjectForm";
import type { AddLxdStepValues, NewPodValues } from "./types";

import { usePools } from "@/app/api/query/pools";
import { useZones } from "@/app/api/query/zones";
import { generalActions } from "@/app/store/general";
import { podActions } from "@/app/store/pod";

export const AddLxdSteps = {
  CREDENTIALS: "Credentials",
  AUTHENTICATION: "Authentication",
  SELECT_PROJECT: "Project selection",
} as const;

export const AddLxd = (): ReactElement => {
  const dispatch = useDispatch();
  const resourcePools = usePools();
  const zones = useZones();
  const [step, setStep] = useState<AddLxdStepValues>(AddLxdSteps.CREDENTIALS);
  const stepIndex = Object.values(AddLxdSteps).indexOf(step);
  const [submissionErrors, setSubmissionErrors] = useState<string | null>(null);
  const [newPodValues, setNewPodValues] = useState<NewPodValues>({
    certificate: "",
    key: "",
    name: "",
    password: "",
    pool: resourcePools.data?.items?.length
      ? `${resourcePools.data?.items[0].id}`
      : "",
    power_address: "",
    zone: zones.data?.items?.length ? `${zones.data?.items[0].id}` : "",
  });

  // We run the cleanup function here rather than in each form component
  // because we want the errors to be able to persist across forms. We also
  // clear projects, so the user has to "re-authenticate" every time.
  // Clear the generated certificate when the entire AddLxd flow ends.
  useEffect(() => {
    return () => {
      dispatch(podActions.cleanup());
      dispatch(podActions.clearProjects());
      dispatch(generalActions.clearGeneratedCertificate());
    };
  }, [dispatch]);

  return (
    <>
      <Stepper activeStep={stepIndex} items={Object.values(AddLxdSteps)} />
      <hr />
      {submissionErrors ? (
        <NotificationBanner
          data-testid="submission-error"
          severity="negative"
          title="Error:"
        >
          {submissionErrors}
        </NotificationBanner>
      ) : null}
      {step === AddLxdSteps.CREDENTIALS && (
        <CredentialsForm
          newPodValues={newPodValues}
          setNewPodValues={setNewPodValues}
          setStep={setStep}
          setSubmissionErrors={setSubmissionErrors}
        />
      )}
      {step === AddLxdSteps.AUTHENTICATION && (
        <AuthenticationForm
          newPodValues={newPodValues}
          setNewPodValues={setNewPodValues}
          setStep={setStep}
        />
      )}
      {step === AddLxdSteps.SELECT_PROJECT && (
        <SelectProjectForm
          newPodValues={newPodValues}
          setStep={setStep}
          setSubmissionErrors={setSubmissionErrors}
        />
      )}
    </>
  );
};

export default AddLxd;
