import { useState } from "react";

import { Col, Input, Row, Select, Tooltip } from "@canonical/react-components";
import { useFormikContext } from "formik";
import pluralize from "pluralize";

import type { ComposeFormDefaults, ComposeFormValues } from "../ComposeForm";

import DomainSelect from "@/app/base/components/DomainSelect";
import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import ResourcePoolSelect from "@/app/base/components/ResourcePoolSelect";
import ShowAdvanced from "@/app/base/components/ShowAdvanced";
import ZoneSelect from "@/app/base/components/ZoneSelect";
import { PodType } from "@/app/store/pod/constants";
import type { Pod } from "@/app/store/pod/types";
import { arrayFromRangesString, getRanges } from "@/app/utils";

type Props = {
  architectures: Pod["architectures"];
  available: {
    cores: number;
    hugepages: number;
    memory: number; // MiB
    pinnedCores: number[];
  };
  defaults: ComposeFormDefaults;
  podType: Pod["type"];
};

const getHugepagesTooltip = (isLxd: boolean, hasFreeHugepages: boolean) => {
  if (!isLxd) {
    return "Hugepages are only supported on LXD KVMs.";
  }
  if (!hasFreeHugepages) {
    return "There are no free hugepages on this system.";
  }
  return null;
};

export const ComposeFormFields = ({
  architectures,
  available,
  defaults,
  podType,
}: Props): React.ReactElement => {
  const { setFieldValue, values } = useFormikContext<ComposeFormValues>();
  const [pinningCores, setPinningCores] = useState(false);
  const coresCaution = available.cores < defaults.cores;
  const memoryCaution = available.memory < defaults.memory;
  const isLxd = podType === PodType.LXD;
  const hasFreeHugepages = available.hugepages > 0;
  const availableCoresString = pluralize("core", available.cores, true);
  const selectedCores = arrayFromRangesString(values.pinnedCores) || [];
  const alreadyPinned = selectedCores.filter(
    (core) => !available.pinnedCores.includes(core)
  );

  return (
    <Row>
      <Col size={12}>
        <FormikField
          label="VM name"
          name="hostname"
          placeholder="Optional"
          type="text"
        />
      </Col>

      <p className="u-no-margin--bottom">Cores</p>
      <Input
        checked={!pinningCores}
        id="not-pinning-cores"
        label="Use any available core(s)"
        onChange={() => {
          setPinningCores(false);
          setFieldValue("cores", defaults.cores).catch((reason: unknown) => {
            throw new FormikFieldChangeError(
              "cores",
              "setFieldValue",
              reason as string
            );
          });
          setFieldValue("pinnedCores", "").catch((reason: unknown) => {
            throw new FormikFieldChangeError(
              "pinnedCores",
              "setFieldValue",
              reason as string
            );
          });
        }}
        type="radio"
      />
      {!pinningCores && (
        <FormikField
          aria-label="Cores"
          help={coresCaution ? undefined : `${availableCoresString} available.`}
          max={`${available.cores}`}
          min="1"
          name="cores"
          placeholder={`${defaults.cores} (default)`}
          step="1"
          type="number"
          wrapperClassName="u-sv2"
        />
      )}
      <Tooltip
        data-testid="core-pin-tooltip"
        message={!isLxd ? "Core pinning is only supported on LXD KVMs" : null}
      >
        <Input
          checked={pinningCores}
          disabled={!isLxd}
          id="pinning-cores"
          label="Pin VM to specific core(s)"
          onChange={() => {
            setPinningCores(true);
            setFieldValue("cores", "").catch((reason: unknown) => {
              throw new FormikFieldChangeError(
                "cores",
                "setFieldValue",
                reason as string
              );
            });
            setFieldValue("pinnedCores", "").catch((reason: unknown) => {
              throw new FormikFieldChangeError(
                "pinnedCores",
                "setFieldValue",
                reason as string
              );
            });
          }}
          type="radio"
        />
      </Tooltip>
      {pinningCores && (
        <FormikField
          aria-label="Pinned cores"
          caution={
            alreadyPinned.length
              ? `The following cores have already been pinned: ${getRanges(
                  alreadyPinned
                )}`
              : null
          }
          help={`${availableCoresString} available (unpinned indices: ${getRanges(
            available.pinnedCores
          )})`}
          name="pinnedCores"
          placeholder='Separate by comma or input a range, e.g. "1,2,4-12"'
          type="text"
          wrapperClassName="u-sv2"
        />
      )}
      <FormikField
        help={memoryCaution ? undefined : `${available.memory}MiB available.`}
        label="RAM (MiB)"
        max={`${available.memory}`}
        min="1024"
        name="memory"
        placeholder={`${defaults.memory} (default)`}
        type="number"
        wrapperClassName="u-sv2"
      />
      <ShowAdvanced>
        <Col size={12}>
          <DomainSelect name="domain" required valueKey="id" />
          <ZoneSelect name="zone" required valueKey="id" />
          <ResourcePoolSelect name="pool" required valueKey="id" />
          <FormikField
            component={Select}
            label="Architecture"
            name="architecture"
            options={[
              { label: "Select architecture", value: "", disabled: true },
              ...architectures.map((architecture) => ({
                key: architecture,
                label: architecture,
                value: architecture,
              })),
            ]}
          />
          <Tooltip
            data-testid="hugepages-tooltip"
            message={getHugepagesTooltip(isLxd, hasFreeHugepages)}
          >
            <FormikField
              disabled={!isLxd || !hasFreeHugepages}
              label="Enable hugepages"
              name="hugepagesBacked"
              type="checkbox"
            />
          </Tooltip>
        </Col>
      </ShowAdvanced>
    </Row>
  );
};

export default ComposeFormFields;
