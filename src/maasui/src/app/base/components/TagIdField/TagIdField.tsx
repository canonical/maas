import type { PropsWithSpread } from "@canonical/react-components";
import { useFormikContext } from "formik";

import TagField from "@/app/base/components/TagField";
import type { Props as TagFieldProps } from "@/app/base/components/TagField/TagField";
import type { Tag as TagSelectorTag } from "@/app/base/components/TagSelector/TagSelector";
import type { AnyObject } from "@/app/base/types";
import type { Tag, TagMeta } from "@/app/store/tag/types";

type Props = PropsWithSpread<
  {
    tagList: Tag[];
    name?: string;
  },
  Omit<TagFieldProps, "tags">
>;

const generateTags = (tagIds: Tag[TagMeta.PK][], tagList: Tag[]) =>
  tagIds.reduce<TagSelectorTag[]>((tags, tagId) => {
    const tag = tagList.find(({ id }) => id === tagId);
    if (tag) {
      tags.push({ id: tag.id, name: tag.name });
    }
    return tags;
  }, []);

const TagIdField = <V extends AnyObject = AnyObject>({
  name = "tags",
  tagList,
  ...props
}: Props): React.ReactElement => {
  const { initialValues } = useFormikContext<V>();
  let initial: Tag[TagMeta.PK][] = [];
  if (name in initialValues && Array.isArray(initialValues[name])) {
    initial = initialValues[name] as Tag[TagMeta.PK][];
  }
  return (
    <TagField
      initialSelected={generateTags(initial, tagList)}
      name={name}
      storedValue="id"
      tags={tagList.map((tag) => ({ id: tag.id, name: tag.name }))}
      {...props}
    />
  );
};

export default TagIdField;
