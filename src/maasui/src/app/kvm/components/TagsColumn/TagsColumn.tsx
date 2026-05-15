import DoubleRow from "@/app/base/components/DoubleRow";

type Props = { tags: string[] };

const TagsColumn = ({ tags }: Props): React.ReactElement | null => {
  return (
    <DoubleRow
      primary={<span data-testid="pod-tags">{tags.join(", ")}</span>}
    />
  );
};

export default TagsColumn;
