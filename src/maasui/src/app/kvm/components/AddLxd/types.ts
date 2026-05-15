import type { ValueOf } from "@canonical/react-components";

import type { AddLxdSteps } from "./AddLxd";

export type AddLxdStepValues = ValueOf<typeof AddLxdSteps>;

export type NewPodValues = {
  certificate: string;
  key: string;
  name: string;
  password: string;
  pool: string;
  power_address: string;
  zone: string;
};

export type CredentialsFormValues = Omit<NewPodValues, "password">;

export type SelectProjectFormValues = {
  existingProject: string;
  newProject: string;
};
