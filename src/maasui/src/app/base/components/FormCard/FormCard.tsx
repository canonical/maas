import type { ReactNode } from "react";

import { Card, Col, Row } from "@canonical/react-components";
import type { ClassName, ColSize } from "@canonical/react-components";
import classNames from "classnames";

import { COL_SIZES } from "@/app/base/constants";
import { useId } from "@/app/base/hooks/base";

type Props = {
  children: ReactNode;
  className?: ClassName;
  highlighted?: boolean;
  sidebar?: boolean;
  stacked?: boolean;
  title?: ReactNode;
};

const getContentSize = (sidebar: boolean, title: ReactNode) => {
  const { CARD_TITLE, SIDEBAR, TOTAL } = COL_SIZES;
  let contentSize = TOTAL;
  if (sidebar) {
    contentSize -= SIDEBAR;
  }
  if (title) {
    contentSize -= CARD_TITLE;
  }
  return contentSize as ColSize;
};

export enum TestIds {
  ColContent = "col-content",
}

export const FormCard = ({
  children,
  className,
  highlighted = true,
  sidebar = true,
  stacked,
  title,
}: Props): React.ReactElement => {
  const id = useId();
  const { CARD_TITLE } = COL_SIZES;
  const contentSize = getContentSize(sidebar, title);
  const titleNode =
    typeof title === "string" ? (
      <h4 className="form-card__title" id={id}>
        {title}
      </h4>
    ) : (
      title
    );
  const content = stacked ? (
    <>
      {titleNode}
      {children}
    </>
  ) : (
    <Row>
      {title && <Col size={CARD_TITLE}>{titleNode}</Col>}
      <Col data-testid={TestIds.ColContent} size={contentSize}>
        {children}
      </Col>
    </Row>
  );
  return (
    <Card
      aria-labelledby={id}
      className={classNames("form-card", className)}
      highlighted={highlighted}
    >
      {content}
    </Card>
  );
};

export default FormCard;
