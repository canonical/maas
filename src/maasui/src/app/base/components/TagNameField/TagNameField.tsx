import type { PropsWithSpread } from "@canonical/react-components";
import { useFormikContext } from "formik";

import TagField from "@/app/base/components/TagField";
import type { Props as TagFieldProps } from "@/app/base/components/TagField/TagField";
import type { AnyObject } from "@/app/base/types";

type Props = PropsWithSpread<
  {
    tagList?: string[] | null;
    name?: string;
  },
  Omit<TagFieldProps, "tags">
>;

const TagNameField = <V extends AnyObject = AnyObject>({
  name = "tags",
  tagList,
  ...props
}: Props): React.ReactElement => {
  const { initialValues } = useFormikContext<V>();
  let initial: string[] = [];
  if (name in initialValues && Array.isArray(initialValues[name])) {
    initial = initialValues[name] as string[];
  }
  return (
    <TagField
      initialSelected={initial.map((tag: string) => ({
        name: tag,
      }))}
      name={name}
      // Populate the list of tags with the provided list or with the initial values list.
      tags={(tagList || [...initial]).map((tag: string) => ({
        name: tag,
      }))}
      {...props}
    />
  );
};

export default TagNameField;
