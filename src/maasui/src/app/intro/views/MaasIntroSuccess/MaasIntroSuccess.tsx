import { Button, List } from "@canonical/react-components";
import { useDispatch } from "react-redux";
import { Link } from "react-router";

import { useGetCurrentUser } from "@/app/api/query/auth";
import urls from "@/app/base/urls";
import IntroCard from "@/app/intro/components/IntroCard";
import IntroSection from "@/app/intro/components/IntroSection";
import { useExitURL } from "@/app/intro/hooks";
import { configActions } from "@/app/store/config";

export enum Labels {
  FinishSetup = "Finish setup",
}

const MaasIntroSuccess = (): React.ReactElement => {
  const dispatch = useDispatch();
  const user = useGetCurrentUser();
  const exitURL = useExitURL();
  const continueLink = user.data?.statistics?.completed_intro
    ? exitURL
    : urls.intro.user;

  return (
    <IntroSection windowTitle="Success">
      <IntroCard
        complete={true}
        data-testid="maas-connectivity-form"
        title="MAAS has been successfully set up"
      >
        <List
          items={[
            "Once DHCP is enabled, set your machines to PXE boot and they will be automatically enlisted in the Machines tab.",
            "Discovered MAC/IP pairs in your network will be listed on your dashboard and can be added to MAAS.",
            "The fabrics, VLANs and subnets in your network will be automatically added to MAAS in the Subnets tab.",
          ]}
        />
      </IntroCard>
      <div className="u-align--right">
        <Button element={Link} to={urls.intro.images}>
          Back
        </Button>
        <Button
          appearance="positive"
          data-testid="continue-button"
          element={Link}
          onClick={() => {
            dispatch(configActions.update({ completed_intro: true }));
          }}
          to={continueLink}
        >
          {Labels.FinishSetup}
        </Button>
      </div>
    </IntroSection>
  );
};

export default MaasIntroSuccess;
