import { Select } from "@canonical/react-components";
import type { PaginationProps } from "@canonical/react-components";

type Props = {
  pageSize: number;
  paginate: NonNullable<PaginationProps["paginate"]>;
  setPageSize: (pageSize: number) => void;
};

export enum Labels {
  ItemsPerPage = "Items per page",
  Fifty = "50/page",
  OneHundred = "100/page",
  TwoHundred = "200/page",
}

const groupOptions = [
  {
    value: 50,
    label: Labels.Fifty,
  },
  {
    value: 100,
    label: Labels.OneHundred,
  },
  {
    value: 200,
    label: Labels.TwoHundred,
  },
];

const PageSizeSelect = ({
  pageSize,
  paginate,
  setPageSize,
}: Props): React.ReactElement => {
  return (
    <Select
      aria-label={Labels.ItemsPerPage}
      className="u-no-margin"
      defaultValue={pageSize}
      onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
        paginate(1);
        setPageSize(parseInt(e.target.value));
      }}
      options={groupOptions}
    />
  );
};

export default PageSizeSelect;
