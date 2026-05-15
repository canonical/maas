import { useClickOutside } from "@canonical/react-components";

const OutsideClickHandler = ({
  children,
  onClick,
}: React.PropsWithChildren<{
  onClick: () => void;
}>): React.ReactElement => {
  const ref = useClickOutside<HTMLDivElement>(onClick);

  return <div ref={ref}>{children}</div>;
};

export default OutsideClickHandler;
