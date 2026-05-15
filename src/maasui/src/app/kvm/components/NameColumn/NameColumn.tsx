import { Link } from "react-router";

import DoubleRow from "@/app/base/components/DoubleRow";

type Props = {
  name: string;
  secondary?: string;
  url: string;
};

const NameColumn = ({
  name,
  secondary,
  url,
}: Props): React.ReactElement | null => {
  return (
    <DoubleRow
      primary={
        <Link to={url}>
          <strong data-testid="name">{name}</strong>
        </Link>
      }
      secondary={secondary}
    />
  );
};

export default NameColumn;
