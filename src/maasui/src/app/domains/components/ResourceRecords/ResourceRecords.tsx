import { MainToolbar } from "@canonical/maas-react-components";
import { Button, Col, Row, Spinner, Strip } from "@canonical/react-components";
import { useSelector } from "react-redux";

import AddRecordForm from "../DomainDetailsHeader/AddRecordForm";

import { useSidePanel } from "@/app/base/side-panel-context";
import { ResourceRecordsTable } from "@/app/domains/components";
import domainsSelectors from "@/app/store/domain/selectors";
import type { Domain } from "@/app/store/domain/types";
import { isDomainDetails } from "@/app/store/domain/utils";
import type { RootState } from "@/app/store/root/types";

export enum Labels {
  NoRecords = "Domain contains no records.",
}

type Props = {
  id: Domain["id"];
};

const ResourceRecords = ({ id }: Props): React.ReactElement | null => {
  const { openSidePanel } = useSidePanel();
  const domain = useSelector((state: RootState) =>
    domainsSelectors.getById(state, id)
  );
  const loading = useSelector(domainsSelectors.loading);

  if (loading) {
    return (
      <Strip shallow>
        <Spinner text="Loading..." />
      </Strip>
    );
  }

  if (!isDomainDetails(domain)) {
    return null;
  }

  return (
    <Strip shallow>
      <Row>
        <Col size={12}>
          <MainToolbar>
            <MainToolbar.Title className="p-heading--4">
              Resource records
            </MainToolbar.Title>
            <MainToolbar.Controls>
              <Button
                data-testid="add-record"
                key="add-record"
                onClick={() => {
                  openSidePanel({
                    component: AddRecordForm,
                    title: "Add record",
                    props: {
                      id,
                    },
                  });
                }}
              >
                Add record
              </Button>
            </MainToolbar.Controls>
          </MainToolbar>
          <ResourceRecordsTable domain={domain} id={id} />
        </Col>
      </Row>
    </Strip>
  );
};

export default ResourceRecords;
