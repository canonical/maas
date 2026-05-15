import { Link } from "@canonical/react-components";

import docsUrls from "@/app/base/docsUrls";
import IntroCard from "@/app/intro/components/IntroCard";
import IntroSection from "@/app/intro/components/IntroSection";

export enum Labels {
  Welcome = "Welcome to MAAS",
  Help = "Help with configuring MAAS",
  Incomplete = "This MAAS has not be configured. Ask an admin to log in and finish the configuration.",
}

const IncompleteCard = (): React.ReactElement => {
  return (
    <IntroSection>
      <IntroCard
        data-testid="maas-name-form"
        hasErrors={true}
        title={Labels.Welcome}
        titleLink={
          <Link href={docsUrls.configurationJourney} target="_blank">
            {Labels.Help}
          </Link>
        }
      >
        <p>{Labels.Incomplete}</p>
      </IntroCard>
    </IntroSection>
  );
};

export default IncompleteCard;
