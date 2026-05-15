import type { ReactElement, ReactNode } from "react";
import { useEffect } from "react";

import type { ClassName } from "@canonical/react-components";
import { usePrevious } from "@canonical/react-components/dist/hooks";
import classNames from "classnames";
import { useLocation } from "react-router";

import type { SectionHeaderProps } from "@/app/base/components/SectionHeader";
import SectionHeader from "@/app/base/components/SectionHeader";
import { useSidePanel } from "@/app/base/side-panel-context";

type TitleBlock = {
  title: ReactNode;
  subtitle?: ReactNode;
};

type Props = {
  buttons?: SectionHeaderProps["buttons"];
  className?: ClassName;
  loading?: SectionHeaderProps["loading"];
  tabLinks: SectionHeaderProps["tabLinks"];
  title: ReactNode;
  titleBlocks: TitleBlock[];
};

const KVMDetailsHeader = ({
  buttons,
  className,
  loading,
  tabLinks,
  title,
  titleBlocks,
}: Props): ReactElement => {
  const location = useLocation();
  const { closeSidePanel } = useSidePanel();
  const pathname = location.pathname;
  const previousPathname = usePrevious(pathname);

  // Close the action form if the pathname changes.
  useEffect(() => {
    if (previousPathname && pathname !== previousPathname) {
      closeSidePanel();
    }
  }, [pathname, previousPathname, closeSidePanel]);

  return (
    <SectionHeader
      buttons={buttons}
      className={classNames("kvm-details-header", className)}
      headerSize="wide"
      loading={loading}
      subtitle={
        <>
          {titleBlocks.map((block, i) => (
            <div
              className="kvm-details-header__title-block"
              data-testid="extra-title-block"
              key={`title-block-${i}`}
            >
              <p
                className="u-text--muted u-no-margin u-no-padding"
                data-testid="block-title"
              >
                {block.title}
              </p>
              <p
                className="u-no-margin u-no-padding"
                data-testid="block-subtitle"
              >
                {block.subtitle || " "}
              </p>
            </div>
          ))}
        </>
      }
      subtitleClassName="kvm-details-header__title-blocks u-flex"
      tabLinks={tabLinks}
      title={title}
    />
  );
};

export default KVMDetailsHeader;
