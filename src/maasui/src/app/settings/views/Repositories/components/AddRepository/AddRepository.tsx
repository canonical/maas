import type { ReactElement } from "react";
import { useEffect } from "react";

import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import { repositorySchema } from "../../constants";
import { getRepositoryTypeString } from "../../utils";
import RepositoryFormFields from "../RepositoryFormFields";
import type { RepositoryFormValues } from "../types";

import { useCreatePackageRepository } from "@/app/api/query/packageRepositories";
import type {
  CreatePackageRepositoryData,
  CreatePackageRepositoryError,
  KnownComponentsEnum,
} from "@/app/apiclient";
import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { generalActions } from "@/app/store/general";
import {
  componentsToDisable as componentsToDisableSelectors,
  knownArchitectures as knownArchitecturesSelectors,
  pocketsToDisable as pocketsToDisableSelectors,
} from "@/app/store/general/selectors";
import { parseCommaSeparatedValues } from "@/app/utils";

type Props = {
  type: "ppa" | "repository";
};

const AddRepository = ({ type }: Props): ReactElement => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const componentsToDisableLoaded = useSelector(
    componentsToDisableSelectors.loaded
  );
  const knownArchitecturesLoaded = useSelector(
    knownArchitecturesSelectors.loaded
  );
  const pocketsToDisableLoaded = useSelector(pocketsToDisableSelectors.loaded);
  const allLoaded =
    componentsToDisableLoaded &&
    knownArchitecturesLoaded &&
    pocketsToDisableLoaded;

  const createRepo = useCreatePackageRepository();

  // Fetch data if not all loaded.
  useEffect(() => {
    if (!allLoaded) {
      dispatch(generalActions.fetchComponentsToDisable());
      dispatch(generalActions.fetchKnownArchitectures());
      dispatch(generalActions.fetchPocketsToDisable());
    }
  }, [dispatch, allLoaded]);

  const typeString = getRepositoryTypeString(type);
  const title = `Add ${typeString}`;
  const initialValues: RepositoryFormValues = {
    arches: ["i386", "amd64"],
    components: "",
    default: false,
    disable_sources: false,
    disabled_components: [],
    disabled_pockets: [],
    distributions: "",
    enabled: true,
    key: "",
    name: "",
    url: type === "ppa" ? "ppa:" : "",
  };

  if (!allLoaded) {
    return <Spinner text="Loading..." />;
  }

  return (
    <FormikForm<RepositoryFormValues, CreatePackageRepositoryError>
      aria-label={title}
      errors={createRepo.error}
      initialValues={initialValues}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Saved",
        category: "Package repos settings",
        label: `${title} form`,
      }}
      onSubmit={(values) => {
        const params: CreatePackageRepositoryData["body"] = {
          arches: values.arches,
          disable_sources: values.disable_sources,
          key: values.key,
          name: values.name,
          url: values.url,
        };

        params.components = parseCommaSeparatedValues(
          values.components
        ) as unknown as KnownComponentsEnum[];
        params.distributions = parseCommaSeparatedValues(values.distributions);
        params.enabled = values.enabled;

        createRepo.mutate({
          body: { ...params },
        });
      }}
      onSuccess={closeSidePanel}
      saved={createRepo.isSuccess}
      saving={createRepo.isPending}
      submitLabel={`Save ${typeString}`}
      validationSchema={repositorySchema}
    >
      <RepositoryFormFields type={type} />
    </FormikForm>
  );
};

export default AddRepository;
