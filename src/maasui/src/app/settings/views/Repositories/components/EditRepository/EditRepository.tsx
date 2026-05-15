import { useEffect } from "react";

import {
  Notification as NotificationBanner,
  Spinner,
} from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import { repositorySchema } from "../../constants";
import {
  getIsDefaultRepo,
  getRepoDisplayName,
  getRepositoryTypeString,
} from "../../utils";
import RepositoryFormFields from "../RepositoryFormFields";
import type { RepositoryFormValues } from "../types";

import {
  useGetPackageRepository,
  useUpdatePackageRepository,
} from "@/app/api/query/packageRepositories";
import type {
  ComponentsToDisableEnum,
  KnownArchesEnum,
  KnownComponentsEnum,
  PackageRepositoryResponse,
  PocketsToDisableEnum,
  UpdatePackageRepositoryData,
  UpdatePackageRepositoryError,
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
  id: PackageRepositoryResponse["id"];
  type: "ppa" | "repository" | undefined;
};

export const EditRepository = ({ id, type }: Props): React.ReactElement => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const componentsToDisableLoaded = useSelector(
    componentsToDisableSelectors.loaded
  );
  const knownArchitecturesLoaded = useSelector(
    knownArchitecturesSelectors.loaded
  );
  const pocketsToDisableLoaded = useSelector(pocketsToDisableSelectors.loaded);

  const {
    isPending,
    isError,
    data: repository,
    error,
  } = useGetPackageRepository({
    path: { package_repository_id: id },
  });
  const eTag = repository?.headers?.get("ETag");
  const updateRepo = useUpdatePackageRepository();

  const allLoaded =
    componentsToDisableLoaded &&
    knownArchitecturesLoaded &&
    pocketsToDisableLoaded;

  // Fetch data if not all loaded.
  useEffect(() => {
    if (!allLoaded) {
      dispatch(generalActions.fetchComponentsToDisable());
      dispatch(generalActions.fetchKnownArchitectures());
      dispatch(generalActions.fetchPocketsToDisable());
    }
  }, [dispatch, allLoaded]);

  if (isPending || !allLoaded) {
    return <Spinner text="Loading..." />;
  }

  if (isError) {
    return (
      <NotificationBanner
        severity="negative"
        title="Error while fetching package repository"
      >
        {error.message}
      </NotificationBanner>
    );
  }

  if (!type || !repository) {
    return <h4>Repository not found</h4>;
  }

  const initialValues: RepositoryFormValues = {
    arches: repository.arches as unknown as KnownArchesEnum[],
    components: repository.components.join(", "),
    default: getIsDefaultRepo(repository),
    disable_sources: repository.disable_sources,
    disabled_components:
      repository.disabled_components as unknown as ComponentsToDisableEnum[],
    disabled_pockets:
      repository.disabled_pockets as unknown as PocketsToDisableEnum[],
    distributions: repository.distributions.join(", "),
    enabled: repository.enabled,
    key: repository.key,
    name: getRepoDisplayName(repository.name),
    url: repository.url,
  };

  const typeString = getRepositoryTypeString(type);
  const title = `Edit ${typeString}`;

  return (
    <FormikForm<RepositoryFormValues, UpdatePackageRepositoryError>
      aria-label={title}
      errors={updateRepo.error}
      initialValues={initialValues}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Saved",
        category: "Package repos settings",
        label: `${title} form`,
      }}
      onSubmit={(values) => {
        const params: UpdatePackageRepositoryData["body"] = {
          arches: values.arches,
          disable_sources: values.disable_sources,
          key: values.key,
          name: values.name,
          url: values.url,
        };

        if (values.default) {
          params.disabled_components = values.disabled_components;
          params.disabled_pockets = values.disabled_pockets;
        } else {
          params.components = parseCommaSeparatedValues(
            values.components
          ) as unknown as KnownComponentsEnum[];
          params.distributions = parseCommaSeparatedValues(
            values.distributions
          );
          params.enabled = values.enabled;
        }

        updateRepo.mutate({
          headers: { ETag: eTag },
          path: { package_repository_id: repository.id },
          body: { ...params },
        });
      }}
      onSuccess={closeSidePanel}
      saved={updateRepo.isSuccess}
      saving={updateRepo.isPending}
      submitLabel={`Save ${typeString}`}
      validationSchema={repositorySchema}
    >
      <RepositoryFormFields type={type} />
    </FormikForm>
  );
};

export default EditRepository;
