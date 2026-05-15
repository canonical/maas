import { useRef } from "react";
import type { ReactNode } from "react";

import classNames from "classnames";
import usePortal from "react-useportal";

type Props = {
  children: ReactNode;
  className?: string;
  content?: ReactNode;
  position?: "left" | "right";
};

const getPositionStyle = (
  el: React.MutableRefObject<Element | null>,
  position: Props["position"]
) => {
  if (!el?.current) {
    return {};
  }

  const dimensions = el.current.getBoundingClientRect();
  const { height, left, right, top } = dimensions;
  const styles: {
    position: string;
    top: number;
    left: number | null;
    right: number | null;
  } = {
    position: "absolute",
    top: top + height + window.scrollY || 0,
    left: null,
    right: null,
  };

  if (position === "left") {
    styles.left = left + window.scrollX || 0;
  } else {
    styles.right = window.innerWidth + window.scrollX - right || 0;
  }
  return styles;
};

const Popover = ({
  children,
  className,
  content,
  position = "right",
}: Props): React.ReactElement => {
  const buttonRef = useRef<HTMLButtonElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const positionStyle = getPositionStyle(buttonRef, position);
  const { openPortal, closePortal, isOpen, Portal } = usePortal();

  const handleBlur = (
    e: React.FocusEvent<HTMLElement> | React.MouseEvent<HTMLElement>
  ) => {
    // do not close if the focus is within the tooltip wrapper
    if (buttonRef?.current?.contains(document.activeElement)) {
      return;
    }

    if (
      e.relatedTarget
        ? !contentRef.current?.contains(e.relatedTarget as Node)
        : e.target !== contentRef.current
    ) {
      closePortal();
    }
  };

  const handleClick: React.MouseEventHandler<HTMLElement> = (e) => {
    // ignore clicks within the tooltip message
    if (contentRef.current?.contains(e.target as Node)) {
      return;
    }
    e.currentTarget.focus();
    openPortal();
  };

  return (
    <button
      className="p-button--base u-no-padding u-no-margin--bottom u-width--100"
      data-testid="popover-container"
      onBlur={handleBlur}
      onClick={handleClick}
      onFocus={openPortal}
      onMouseOut={handleBlur}
      onMouseOver={openPortal}
      ref={buttonRef}
    >
      {children}
      {isOpen && content && (
        <Portal>
          <div
            className={classNames("p-popover", className)}
            onClick={handleClick}
            ref={contentRef}
            style={positionStyle}
          >
            {content}
          </div>
        </Portal>
      )}
    </button>
  );
};

export default Popover;
