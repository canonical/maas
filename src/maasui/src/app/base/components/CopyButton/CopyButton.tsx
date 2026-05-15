import { useRef, useState } from "react";

import { Button } from "@canonical/react-components";

type Props = {
  value: string;
};

const CopyButton = ({ value }: Props): React.ReactElement => {
  const input = useRef<HTMLInputElement>(null);
  const [icon, setIcon] = useState("copy");

  const resetIcon = (timeout = 1000) => {
    setTimeout(() => {
      setIcon("copy");
    }, timeout);
  };

  const handleClick = () => {
    if (input.current !== null) {
      // To copy the value the input must be visible, so temporarily display the input as text.
      input.current.type = "text";
      input.current.focus();
      input.current.select();
      try {
        document.execCommand("copy");
        setIcon("success");
      } catch {
        // eslint-disable-next-line no-console
        console.error("Copy was unsuccessful");
        setIcon("warning");
      }
      resetIcon();
      // Copying is done so hide the input again.
      input.current.type = "hidden";
    }
  };
  return (
    <>
      <Button
        appearance="base"
        className="is-dense u-table-cell-padding-overlap u-no-margin--right"
        hasIcon
        onClick={handleClick}
        type="button"
      >
        <i className={`p-icon--${icon}`}>Copy</i>
      </Button>
      <input ref={input} type="hidden" value={value} />
    </>
  );
};

export default CopyButton;
