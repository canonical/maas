import { useFormikContext } from "formik";

import FormikField from "@/app/base/components/FormikField";
import type { Props as FormikFieldProps } from "@/app/base/components/FormikField/FormikField";
import TagSelector from "@/app/base/components/TagSelector";
import type {
  Props as TagSelectorProps,
  Tag as TagSelectorTag,
} from "@/app/base/components/TagSelector/TagSelector";
import type { AnyObject } from "@/app/base/types";

export type Props = Omit<Partial<FormikFieldProps>, "name"> &
  Omit<Partial<TagSelectorProps>, "tags"> & {
    storedValue?: "id" | "name";
    name: string;
    tags: TagSelectorProps["tags"];
  };

export enum Label {
  Input = "Tags",
}

const TagField = <V extends AnyObject = AnyObject>({
  storedValue = "name",
  name,
  tags,
  ...props
}: Props): React.ReactElement => {
  const { setFieldValue } = useFormikContext<V>();

  return (
    <FormikField
      allowNewTags
      component={TagSelector}
      label={Label.Input}
      name={name}
      onTagsUpdate={(tags: TagSelectorTag[]) =>
        setFieldValue(
          name,
          tags.map((tag) => tag[storedValue])
        )
      }
      tags={[...tags].sort((a, b) => a.name.localeCompare(b.name))}
      {...props}
    />
  );
};

export default TagField;
