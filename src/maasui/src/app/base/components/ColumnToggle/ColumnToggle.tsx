import type { ReactNode } from "react";
import { useRef } from "react";

import { Button, Icon } from "@canonical/react-components";

type Props = {
  isExpanded: boolean;
  label: ReactNode;
  onClose: () => void;
  onOpen: () => void;
};

const ColumnToggle = ({
  isExpanded,
  label,
  onClose,
  onOpen,
}: Props): React.ReactElement => {
  const buttonNode = useRef<HTMLButtonElement | null>(null);
  return (
    <Button
      appearance="link"
      aria-label="Show/hide details"
      className="column-toggle u-flex--between u-no-margin u-no-padding"
      onClick={() => {
        if (isExpanded) {
          onClose();
        } else {
          onOpen();
          // Delay the scroll check until the toggle is complete.
          window.requestAnimationFrame(() => {
            if (buttonNode.current) {
              const { top } = buttonNode.current.getBoundingClientRect();
              // When a section opens check that it does not get moved off screen,
              // and if it does, scroll it into view.
              if (window.scrollY + top < window.scrollY) {
                window.scrollTo(0, window.scrollY + top);
              }
            }
          });
        }
      }}
    >
      <span className="u-flex--grow u-nudge-left--small" ref={buttonNode}>
        {label}
      </span>
      <Icon
        className="u-flex--no-shrink"
        name={`chevron-${isExpanded ? "up" : "down"}`}
      />
    </Button>
  );
};

export default ColumnToggle;
