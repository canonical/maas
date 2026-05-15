import type { ReactElement, ReactNode } from "react";
import { useEffect } from "react";

import {
  Notification as NotificationBanner,
  Spinner,
} from "@canonical/react-components";
import { useNavigate } from "react-router";

import PageContent from "@/app/base/components/PageContent";
import type { PageContentProps } from "@/app/base/components/PageContent/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import type { APIError, SyncNavigateFunction } from "@/app/base/types";
import { useExitURL } from "@/app/intro/hooks";
import { formatErrors } from "@/app/utils";

type Props = Partial<PageContentProps> & {
  children: ReactNode;
  complete?: boolean;
  errors?: APIError;
  loading?: boolean;
  shouldExitIntro?: boolean;
  titleLink?: ReactNode;
  windowTitle?: string;
};

const IntroSection = ({
  children,
  complete,
  errors,
  loading,
  shouldExitIntro,
  titleLink,
  windowTitle,
  ...props
}: Props): ReactElement => {
  const navigate: SyncNavigateFunction = useNavigate();
  const errorMessage = formatErrors(errors);
  const exitURL = useExitURL();

  useWindowTitle(windowTitle ? `Welcome - ${windowTitle}` : "Welcome");

  useEffect(() => {
    if (shouldExitIntro) {
      navigate(exitURL, { replace: true });
    }
  }, [navigate, exitURL, shouldExitIntro]);

  return (
    <PageContent {...props}>
      {errorMessage && (
        <NotificationBanner severity="negative" title="Error:">
          {errorMessage}
        </NotificationBanner>
      )}
      {loading ? <Spinner text="Loading..." /> : children}
    </PageContent>
  );
};

export default IntroSection;
