import { Button } from "@canonical/react-components";
import pluralize from "pluralize";

type Props = {
  available: number;
  filterSelected?: () => void;
  modelName: string;
  selected?: number;
};

const getSubtitleString = (
  available: number,
  modelName: string,
  selected: number
) => {
  if (available === 0) {
    return `No ${modelName}s available`;
  } else if (selected === available) {
    return `All ${modelName}s selected`;
  } else {
    const nodeCountString = pluralize(modelName, available, true);

    if (selected) {
      return `${selected} of ${nodeCountString} selected`;
    } else {
      return `${nodeCountString} available`;
    }
  }
};

export enum TestIds {
  Filter = "filter-selected",
  Subtitle = "subtitle-string",
}

export const ModelListSubtitle = ({
  available,
  filterSelected,
  modelName,
  selected = 0,
}: Props): React.ReactElement => {
  const subtitleString = getSubtitleString(available, modelName, selected);
  const showFilterButton = selected && selected !== available && filterSelected;

  if (showFilterButton) {
    return (
      <Button
        appearance="link"
        className="u-no-margin--bottom"
        data-testid={TestIds.Filter}
        onClick={filterSelected}
      >
        {subtitleString}
      </Button>
    );
  }
  return (
    <span className="u-text--muted" data-testid={TestIds.Subtitle}>
      {subtitleString}
    </span>
  );
};

export default ModelListSubtitle;
