import { Link } from "react-router";

import type { Tag } from "@/app/store/tag/types";

type Props<T extends Tag | string> = {
  getLinkURL: (tag: T) => string;
  tags: T[];
};

const getTagName = <T extends Tag | string>(tag: T) =>
  typeof tag === "string" ? tag : tag.name;

const TagLinks = <T extends Tag | string>({
  getLinkURL,
  tags,
}: Props<T>): React.ReactElement => {
  const sortedTags = [...tags].sort((a, b) =>
    getTagName(a).localeCompare(getTagName(b))
  );
  return (
    <span className="u-break-word">
      {sortedTags.map((tag, i) => {
        const tagName = getTagName(tag);
        const url = getLinkURL(tag);
        return (
          <span key={tagName}>
            <Link to={url}>{tagName}</Link>
            {i !== tags.length - 1 && ", "}
          </span>
        );
      })}
    </span>
  );
};

export default TagLinks;
