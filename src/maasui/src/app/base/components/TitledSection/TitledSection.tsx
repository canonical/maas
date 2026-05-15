import { createElement } from "react";
import type { ReactNode } from "react";

import { Col, Row, Strip } from "@canonical/react-components";
import type {
  PropsWithSpread,
  StripProps,
  Headings,
} from "@canonical/react-components";

import VisuallyHidden from "../VisuallyHidden";

import { useId } from "@/app/base/hooks/base";

export type Props = PropsWithSpread<
  {
    buttons?: ReactNode;
    children?: ReactNode;
    hasSidebarTitle?: boolean;
    headingElement?: Headings;
    headingClassName?: string;
    headingVisuallyHidden?: boolean;
    title: ReactNode;
  },
  StripProps
>;

type HeadingProps = {
  element: Headings;
  className?: string;
  id: string;
  children: ReactNode;
};

const Heading = ({ element, id, className, children }: HeadingProps) =>
  createElement(
    element,
    {
      id,
      className,
    },
    children
  );

const TitledSection = ({
  buttons,
  children,
  hasSidebarTitle = false,
  headingClassName = "p-heading--4",
  headingElement = "h2",
  headingVisuallyHidden, // hide the title visually (visibly hidden but still accessible)
  shallow = true,
  title,
  ...stripProps
}: Props): React.ReactElement => {
  const id = useId();
  const heading = (
    <Heading className={headingClassName} element={headingElement} id={id}>
      {title}
    </Heading>
  );
  const titleElement = headingVisuallyHidden ? (
    <VisuallyHidden>{heading}</VisuallyHidden>
  ) : (
    heading
  );

  return (
    <Strip
      aria-labelledby={id}
      data-testid="titled-section"
      element="section"
      shallow={shallow}
      {...stripProps}
    >
      {hasSidebarTitle ? (
        <Row data-testid="has-sidebar-title">
          <Col size={3}>
            <div className="u-flex--between u-flex--wrap">
              {titleElement}
              {buttons && <div className="u-hide--large">{buttons}</div>}
            </div>
          </Col>
          <Col size={buttons ? 6 : 9}>{children}</Col>
          {buttons && (
            <Col className="u-align--right" size={3}>
              <div className="u-hide--small u-hide--medium">{buttons}</div>
            </Col>
          )}
        </Row>
      ) : (
        <>
          <div
            className="u-flex--between u-flex--wrap"
            data-testid="has-fullspan-title"
          >
            {titleElement}
            {buttons && <div>{buttons}</div>}
          </div>
          {children}
        </>
      )}
    </Strip>
  );
};

export default TitledSection;
