import { useMemo } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";

import type { FormValues } from "../EditBootArchitectures";

import useBootArchitecturesColumns from "./useBootArchitecturesColumns/useBootArchitecturesColumns";

import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import { knownBootArchitectures as knownBootArchitecturesSelectors } from "@/app/store/general/selectors";
import type { KnownBootArchitecture } from "@/app/store/general/types";

import "./_index.scss";

export enum Headers {
  BootloaderArch = "Bootloader architecture",
  BootMethod = "BIOS boot method",
  Name = "Name",
  Octet = "Architecture octet",
  Protocol = "Protocol",
}

export const BootArchitecturesTable = (): React.ReactElement => {
  const {
    setFieldValue,
    values: { disabled_boot_architectures },
  } = useFormikContext<FormValues>();
  const knownBootArchitectures = useSelector(
    knownBootArchitecturesSelectors.get
  );

  const isChecked = (bootArchName: KnownBootArchitecture["name"]) =>
    !disabled_boot_architectures.includes(bootArchName);

  const handleArchChange = (bootArchName: KnownBootArchitecture["name"]) => {
    setFieldValue(
      "disabled_boot_architectures",
      isChecked(bootArchName)
        ? [...disabled_boot_architectures, bootArchName]
        : disabled_boot_architectures.filter((item) => item !== bootArchName)
    ).catch((reason: unknown) => {
      throw new FormikFieldChangeError(
        "disabled_boot_architectures",
        "setFieldValue",
        reason as string
      );
    });
  };

  // GenericTable requires items in data to have an `id`, but boot archictures do not have these.
  const data = useMemo(
    () => knownBootArchitectures.map((arch, i) => ({ ...arch, id: i })),
    [knownBootArchitectures]
  );

  const columns = useBootArchitecturesColumns({
    isChecked,
    handleArchChange,
    disabledBootArches: disabled_boot_architectures,
  });

  return (
    <GenericTable
      className="boot-architectures-table"
      columns={columns}
      data={data}
      isLoading={false}
      sorting={[{ id: "name", desc: false }]}
    />
  );
};

export default BootArchitecturesTable;
