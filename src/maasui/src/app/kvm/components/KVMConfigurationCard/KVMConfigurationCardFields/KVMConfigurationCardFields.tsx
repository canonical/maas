import * as React from "react";

import { Col, Input, Row, Slider } from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";

import type { KVMConfigurationValues } from "../KVMConfigurationCard";

import FormikField from "@/app/base/components/FormikField";
import ResourcePoolSelect from "@/app/base/components/ResourcePoolSelect";
import TagNameField from "@/app/base/components/TagNameField";
import ZoneSelect from "@/app/base/components/ZoneSelect";
import { PodType } from "@/app/store/pod/constants";
import { formatHostType } from "@/app/store/pod/utils";
import tagSelectors from "@/app/store/tag/selectors";

type Props = {
  zoneDisabled?: boolean;
};

const KVMConfigurationCardFields = ({
  zoneDisabled = false,
}: Props): React.ReactElement => {
  const tags = useSelector(tagSelectors.all);
  const { setFieldValue, values } = useFormikContext<KVMConfigurationValues>();

  return (
    <Row>
      <Col size={5}>
        <Input
          aria-label="KVM host type"
          disabled
          label="KVM host type"
          name="type"
          type="text"
          value={formatHostType(values.type)}
        />
        <ZoneSelect
          disabled={zoneDisabled}
          name="zone"
          required
          valueKey="id"
        />
        <ResourcePoolSelect name="pool" required valueKey="id" />
        <TagNameField tagList={tags.map(({ name }) => name)} />
      </Col>
      <Col size={5}>
        <FormikField
          disabled
          label="Address"
          name="power_address"
          type="text"
        />
        {values.type === PodType.VIRSH && (
          <FormikField
            label="Password (optional)"
            name="power_pass"
            type="password"
          />
        )}
        <FormikField
          component={Slider}
          inputDisabled
          label="CPU overcommit"
          max={10}
          min={0.1}
          name="cpu_over_commit_ratio"
          onChange={(e: React.FormEvent<HTMLInputElement>) =>
            setFieldValue(
              "cpu_over_commit_ratio",
              Number(e.currentTarget.value)
            )
          }
          showInput
          step={0.1}
          value={values.cpu_over_commit_ratio}
        />
        <FormikField
          component={Slider}
          inputDisabled
          label="Memory overcommit"
          max={10}
          min={0.1}
          name="memory_over_commit_ratio"
          onChange={(e: React.FormEvent<HTMLInputElement>) =>
            setFieldValue(
              "memory_over_commit_ratio",
              Number(e.currentTarget.value)
            )
          }
          showInput
          step={0.1}
          value={values.memory_over_commit_ratio}
        />
      </Col>
    </Row>
  );
};

export default KVMConfigurationCardFields;
