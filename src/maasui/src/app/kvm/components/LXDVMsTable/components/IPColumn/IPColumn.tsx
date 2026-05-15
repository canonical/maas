import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import { IPV4_REGEX } from "@/app/base/validation";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";

type Props = {
  systemId: Machine["system_id"];
  version: 4 | 6;
};

const IPColumn = ({ systemId, version }: Props): React.ReactElement => {
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );

  if (!machine) {
    return <Spinner />;
  }

  const ips =
    machine.ip_addresses?.reduce<string[]>((ips, { ip }) => {
      if (
        (version === 4 && IPV4_REGEX.test(ip)) ||
        (version === 6 && !IPV4_REGEX.test(ip))
      ) {
        ips.push(ip);
      }
      return ips;
    }, []) || [];
  return (
    <>
      {ips.length
        ? ips.map((ip) => (
            <div data-testid="ip" key={ip}>
              {ip}
            </div>
          ))
        : "-"}
    </>
  );
};

export default IPColumn;
