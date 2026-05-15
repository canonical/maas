import type { ReactNode } from "react";

import { Pagination } from "@canonical/maas-react-components";
import type { SearchBoxProps } from "@canonical/react-components";

import SearchBox from "@/app/base/components/SearchBox";

type Props = {
  actions?: ReactNode;
  currentPage: number;
  loading?: boolean;
  itemCount: number;
  onSearchChange: SearchBoxProps["onChange"];
  pageSize?: number;
  searchFilter: string;
  setCurrentPage: (page: number) => void;
};

const ActionBar = ({
  actions,
  currentPage,
  loading,
  itemCount,
  onSearchChange,
  pageSize = 50,
  searchFilter,
  setCurrentPage,
  ...props
}: Props): React.ReactElement | null => {
  return (
    <div className="action-bar" {...props}>
      {actions && <div className="action-bar__actions">{actions}</div>}
      <div className="action-bar__search u-flex--grow">
        <SearchBox
          className="u-no-margin--bottom"
          externallyControlled
          onChange={onSearchChange}
          value={searchFilter}
        />
      </div>
      <div className="action-bar__pagination">
        <div className="u-flex--between u-flex--align-baseline u-flex--wrap">
          <Pagination
            aria-label="pagination"
            currentPage={currentPage}
            disabled={loading || itemCount === 0}
            onInputBlur={() => {}}
            onInputChange={(e) => {
              setCurrentPage(Number(e.target.value));
            }}
            onNextClick={() => {
              setCurrentPage(currentPage + 1);
            }}
            onPreviousClick={() => {
              setCurrentPage(currentPage - 1);
            }}
            totalPages={Math.ceil(itemCount / pageSize)}
          />
        </div>
      </div>
    </div>
  );
};

export default ActionBar;
