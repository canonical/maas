import { useEffect } from "react";

import { ContentSection } from "@canonical/maas-react-components";
import { Spinner } from "@canonical/react-components";
import { useSelector, useDispatch } from "react-redux";

import CommissioningForm from "../CommissioningForm";

import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { configActions } from "@/app/store/config";
import configSelectors from "@/app/store/config/selectors";
import { generalActions } from "@/app/store/general";
import { osInfo as osInfoSelectors } from "@/app/store/general/selectors";

export enum Labels {
  Loading = "Loading...",
}

const Commissioning = (): React.ReactElement => {
  const configLoaded = useSelector(configSelectors.loaded);
  const configLoading = useSelector(configSelectors.loading);
  const osInfoLoaded = useSelector(osInfoSelectors.loaded);
  const osInfoLoading = useSelector(osInfoSelectors.loading);
  const loaded = configLoaded && osInfoLoaded;
  const loading = configLoading || osInfoLoading;
  const dispatch = useDispatch();

  useWindowTitle("Commissioning");

  useEffect(() => {
    if (!loaded) {
      dispatch(configActions.fetch());
      dispatch(generalActions.fetchOsInfo());
    }
  }, [dispatch, loaded]);

  return (
    <PageContent>
      <ContentSection variant="narrow">
        <ContentSection.Title className="section-header__title">
          Commissioning
        </ContentSection.Title>
        <ContentSection.Content>
          {loading && <Spinner text={Labels.Loading} />}
          {loaded && <CommissioningForm />}
        </ContentSection.Content>
      </ContentSection>
    </PageContent>
  );
};

export default Commissioning;
