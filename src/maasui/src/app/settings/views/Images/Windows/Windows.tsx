import { useEffect } from "react";

import { ContentSection } from "@canonical/maas-react-components";
import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import WindowsForm from "../WindowsForm";

import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { configActions } from "@/app/store/config";
import configSelectors from "@/app/store/config/selectors";

export enum Labels {
  Loading = "Loading...",
}

const Windows = (): React.ReactElement => {
  const loaded = useSelector(configSelectors.loaded);
  const loading = useSelector(configSelectors.loading);
  const dispatch = useDispatch();

  useWindowTitle("Windows");

  useEffect(() => {
    if (!loaded) {
      dispatch(configActions.fetch());
    }
  }, [dispatch, loaded]);

  return (
    <PageContent>
      <ContentSection variant="narrow">
        <ContentSection.Title className="section-header__title">
          Windows
        </ContentSection.Title>
        <ContentSection.Content>
          {loading && <Spinner text={Labels.Loading} />}
          {loaded && <WindowsForm />}
        </ContentSection.Content>
      </ContentSection>
    </PageContent>
  );
};

export default Windows;
