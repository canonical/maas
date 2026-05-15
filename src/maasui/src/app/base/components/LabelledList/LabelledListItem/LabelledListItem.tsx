import type { ListItem } from "../LabelledList";

import { useId } from "@/app/base/hooks/base";

type Props = {
  item: ListItem;
};

const LabelledListItem = ({ item }: Props): React.ReactElement => {
  const id = useId();
  return (
    <>
      <div className="p-list__item-label" id={id}>
        {item.label}
      </div>
      <div aria-labelledby={id} className="p-list__item-value">
        {item.value}
      </div>
    </>
  );
};

export default LabelledListItem;
