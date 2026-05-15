import { useSelector } from "react-redux";

import { useZones } from "@/app/api/query/zones";
import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { DomainListHeader, DomainsTable } from "@/app/domains/components";
import domainsSelectors from "@/app/store/domain/selectors";

const DomainsList = (): React.ReactElement => {
  const domains = useSelector(domainsSelectors.all);

  useWindowTitle("DNS");
  useZones();

  return (
    <PageContent header={<DomainListHeader />}>
      {domains.length > 0 && <DomainsTable />}
    </PageContent>
  );
};

export default DomainsList;
