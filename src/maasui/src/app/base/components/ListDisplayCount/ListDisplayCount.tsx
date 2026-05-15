export const getCurrentPageDisplayedCount = (
  count: number | null,
  pageSize: number,
  currentPage: number
): number => {
  if (!count) {
    return 0;
  }

  const totalPages = Math.ceil(count / pageSize);

  if (currentPage === totalPages) {
    return pageSize - (totalPages * pageSize - count);
  } else {
    return pageSize;
  }
};

export const ListDisplayCount = ({
  count,
  pageSize,
  currentPage,
  type = "item",
}: {
  count: number;
  pageSize: number;
  currentPage: number;
  type: string;
}): React.ReactElement => {
  return (
    <strong className="machine-list--display-count">
      Showing {getCurrentPageDisplayedCount(count, pageSize, currentPage)} out
      of {count} {type}s
    </strong>
  );
};

export default ListDisplayCount;
