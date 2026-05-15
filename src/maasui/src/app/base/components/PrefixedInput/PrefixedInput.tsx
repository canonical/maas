import type { ReactElement } from "react";
import { useLayoutEffect, useRef } from "react";

import type { InputProps } from "@canonical/react-components";
import { Input } from "@canonical/react-components";
import classNames from "classnames";

export type PrefixedInputProps = Omit<InputProps, "type"> & {
  immutableText: string;
};

const PrefixedInput = ({
  immutableText,
  ...props
}: PrefixedInputProps): ReactElement => {
  const prefixTextRef = useRef<HTMLDivElement>(null);
  const inputWrapperRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const prefixElement = prefixTextRef.current;
    const inputElement = inputWrapperRef.current?.querySelector("input");

    if (prefixElement && inputElement) {
      // Adjust the left padding of the input to be the same width as the immutable octets.
      // This displays the user input and the unchangeable text together as one IP address.
      const prefixWidth = prefixElement.getBoundingClientRect().width;
      inputElement.style.paddingLeft = `${prefixWidth}px`;
    }
  }, [immutableText, props.label]);

  return (
    <div
      className={classNames("prefixed-input", {
        "prefixed-input--with-label": !!props.label,
      })}
    >
      <div className="prefixed-input__text" ref={prefixTextRef}>
        {immutableText}
      </div>
      <div ref={inputWrapperRef}>
        <Input
          className={classNames("prefixed-input__input", props.className)}
          type="text"
          wrapperClassName={classNames(
            "prefixed-input__wrapper",
            props.wrapperClassName
          )}
          {...props}
        />
      </div>
    </div>
  );
};

export default PrefixedInput;
