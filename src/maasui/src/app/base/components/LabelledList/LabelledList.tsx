import type { ReactNode } from "react";

import { List } from "@canonical/react-components";
import classNames from "classnames";

import LabelledListItem from "./LabelledListItem";

export type ListItem = {
  label: ReactNode;
  value: ReactNode;
};

type Props = {
  className?: string;
  items: ListItem[];
};

const LabelledList = ({
  className,
  items,
  ...props
}: Props): React.ReactElement => {
  return (
    <List
      {...props}
      className={classNames("p-list--labelled", className)}
      items={items.map((item) => (
        <LabelledListItem item={item} />
      ))}
    />
  );
};

export default LabelledList;
