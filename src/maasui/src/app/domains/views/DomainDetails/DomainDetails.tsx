import { useEffect } from "react";

import { useDispatch, useSelector } from "react-redux";

import ModelNotFound from "@/app/base/components/ModelNotFound";
import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { useGetURLId } from "@/app/base/hooks/urls";
import urls from "@/app/base/urls";
import {
  DomainDetailsHeader,
  DomainSummary,
  ResourceRecords,
} from "@/app/domains/components";
import { domainActions } from "@/app/store/domain";
import domainsSelectors from "@/app/store/domain/selectors";
import { DomainMeta } from "@/app/store/domain/types";
import type { RootState } from "@/app/store/root/types";
import { isId } from "@/app/utils";

const DomainDetails = (): React.ReactElement => {
  const id = useGetURLId(DomainMeta.PK);
  const domain = useSelector((state: RootState) =>
    domainsSelectors.getById(state, Number(id))
  );
  const domainsLoading = useSelector(domainsSelectors.loading);

  const dispatch = useDispatch();
  useWindowTitle(domain?.name ?? "Loading...");

  useEffect(() => {
    if (isId(id)) {
      dispatch(domainActions.get(id));
      // Set domain as active to ensure all domain data is sent from the server.
      dispatch(domainActions.setActive(id));
    }
    // Unset active domain on cleanup.
    return () => {
      dispatch(domainActions.setActive(null));
    };
  }, [dispatch, id]);

  if (!isId(id) || (!domainsLoading && !domain)) {
    return (
      <ModelNotFound id={id} linkURL={urls.domains.index} modelName="domain" />
    );
  }

  return (
    <PageContent header={<DomainDetailsHeader id={id} />}>
      <DomainSummary id={id} />
      <ResourceRecords id={id} />
    </PageContent>
  );
};

export default DomainDetails;
