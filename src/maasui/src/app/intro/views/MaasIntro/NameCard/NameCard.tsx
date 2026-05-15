import { Col, Link, Row } from "@canonical/react-components";
import { useFormikContext } from "formik";

import type { MaasIntroValues } from "../types";

import FormikField from "@/app/base/components/FormikField";
import docsUrls from "@/app/base/docsUrls";
import IntroCard from "@/app/intro/components/IntroCard";

export enum Labels {
  Welcome = "Welcome to MAAS",
  Help = "Help with configuring MAAS",
  Name = "Region name",
}

const NameCard = (): React.ReactElement => {
  const { errors } = useFormikContext<MaasIntroValues>();

  return (
    <IntroCard
      complete={!errors.name}
      data-testid="maas-name-form"
      hasErrors={!!errors.name}
      title={Labels.Welcome}
      titleLink={
        <Link href={docsUrls.configurationJourney} target="_blank">
          {Labels.Help}
        </Link>
      }
    >
      <Row>
        <Col size={6}>
          <FormikField
            label={Labels.Name}
            name="name"
            placeholder="e.g. us-west"
            type="text"
          />
        </Col>
      </Row>
    </IntroCard>
  );
};

export default NameCard;
