import Definition from "@/app/base/components/Definition";
import type { PowerField } from "@/app/store/general/types";
import { PowerFieldType } from "@/app/store/general/types";
import type { PowerParameter } from "@/app/store/types/node";

type Props = {
  field: PowerField;
  powerParameter: PowerParameter;
};

const getParameterDescription = (
  field: PowerField,
  powerParameter: PowerParameter
) => {
  if (
    field.field_type === PowerFieldType.CHOICE &&
    typeof powerParameter === "string"
  ) {
    const selectedChoice = field.choices.find(
      ([choiceValue]) => choiceValue === powerParameter
    );
    if (selectedChoice) {
      const [, choiceLabel] = selectedChoice;
      return choiceLabel;
    }
  } else if (
    field.field_type === PowerFieldType.MULTIPLE_CHOICE &&
    Array.isArray(powerParameter)
  ) {
    return field.choices
      .reduce<string[]>((labels, [choiceValue, choiceLabel]) => {
        if (powerParameter.includes(choiceValue)) {
          labels.push(choiceLabel);
        }
        return labels;
      }, [])
      .join(", ");
  } else if (field.field_type === PowerFieldType.PASSWORD) {
    return powerParameter.toString().replace(/./g, "*");
  }
  return powerParameter.toString();
};

const PowerParameterDefinition = ({
  field,
  powerParameter,
}: Props): React.ReactElement => {
  const description = getParameterDescription(field, powerParameter);
  return (
    <Definition
      description={description}
      key={field.name}
      label={field.label}
    />
  );
};

export default PowerParameterDefinition;
