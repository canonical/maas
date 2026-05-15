import DoubleRow from "@/app/base/components/DoubleRow";

type Props = {
  version?: string;
  vms: number;
};

const VMsColumn = ({ version, vms }: Props): React.ReactElement | null => {
  return (
    <DoubleRow
      primary={<span data-testid="machines-count">{vms}</span>}
      primaryClassName="u-align--left"
      secondary={version && <span data-testid="version">{version}</span>}
    />
  );
};

export default VMsColumn;
