import { Children } from "react";

import { useId } from "@/app/base/hooks/base";

type CommonProps = {
  label: React.ReactNode;
};

type DescriptionProps =
  | {
      children?: never;
      description?: string;
    }
  | {
      children?: React.ReactNode;
      description?: never;
    };

type Props = CommonProps & DescriptionProps;

const Definition = ({
  label,
  children,
  description,
}: Props): React.ReactElement => {
  const id = useId();
  return (
    <div>
      <p className="u-text--muted" id={id}>
        {label}
      </p>
      {description ? (
        <p aria-labelledby={id}>{description}</p>
      ) : Children.toArray(children).filter((child) => child !== "").length >
        0 ? (
        Children.map(
          children,
          (child, i) =>
            child && (
              <p aria-labelledby={id} key={i}>
                {child}
              </p>
            )
        )
      ) : (
        <p>—</p>
      )}
    </div>
  );
};

export default Definition;
