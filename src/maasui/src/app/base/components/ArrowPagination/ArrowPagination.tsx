import type { HTMLProps } from "react";

import { Button, Icon, Spinner } from "@canonical/react-components";

type Props = HTMLProps<HTMLElement> & {
  currentPage: number;
  itemCount: number;
  loading?: boolean;
  pageSize: number;
  setCurrentPage: (page: number) => void;
  showPageBounds?: boolean;
};

const getBounds = (
  itemCount: number,
  currentPage: number,
  pageSize: number
) => {
  const lowerBound = itemCount === 0 ? 0 : pageSize * (currentPage - 1) + 1;
  const upperBound =
    itemCount > pageSize * currentPage ? pageSize * currentPage : itemCount;
  return `${lowerBound} - ${upperBound} of ${itemCount}`;
};

export enum Labels {
  GoBack = "Go back a page",
  GoForward = "Go forward a page",
  LoadingPagination = "Loading pagination",
}

export enum TestIds {
  PageBounds = "page-bounds",
}

const ArrowPagination = ({
  currentPage,
  itemCount,
  loading = false,
  pageSize,
  setCurrentPage,
  showPageBounds = false,
  ...props
}: Props): React.ReactElement => {
  const onFirstPage = currentPage === 1;
  const onLastPage =
    itemCount === 0 || currentPage === Math.ceil(itemCount / pageSize);

  return (
    <nav aria-label="pagination" {...props}>
      {showPageBounds && (
        <span
          className="u-text--muted u-nudge-left"
          data-testid={TestIds.PageBounds}
        >
          {loading ? (
            <Spinner aria-label={Labels.LoadingPagination} />
          ) : (
            getBounds(itemCount, currentPage, pageSize)
          )}
        </span>
      )}
      <Button
        appearance="base"
        aria-label={Labels.GoBack}
        className="u-no-margin--right u-no-margin--bottom"
        disabled={onFirstPage}
        hasIcon
        onClick={() => {
          setCurrentPage(currentPage - 1);
        }}
      >
        <Icon className="u-rotate-right" name="chevron-down" />
      </Button>
      <Button
        appearance="base"
        aria-label={Labels.GoForward}
        className="u-no-margin--bottom"
        disabled={onLastPage}
        hasIcon
        onClick={() => {
          setCurrentPage(currentPage + 1);
        }}
      >
        <Icon className="u-rotate-left" name="chevron-down" />
      </Button>
    </nav>
  );
};

export default ArrowPagination;
