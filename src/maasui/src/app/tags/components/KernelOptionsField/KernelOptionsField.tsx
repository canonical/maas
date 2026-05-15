import { ExternalLink } from "@canonical/maas-react-components";
import { Textarea } from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";

import FormikField from "@/app/base/components/FormikField";
import docsUrls from "@/app/base/docsUrls";
import { useFetchMachineCount } from "@/app/store/machine/utils/hooks";
import type { RootState } from "@/app/store/root/types";
import tagSelectors from "@/app/store/tag/selectors";
import type {
  CreateParams,
  Tag,
  TagMeta,
  UpdateParams,
} from "@/app/store/tag/types";
import { FetchNodeStatus } from "@/app/store/types/node";
import { isId } from "@/app/utils";

export enum Label {
  KernelOptions = "Kernel options",
}

export type Props = {
  deployedMachinesCount?: number;
  generateDeployedMessage?: (count: number) => string;
  id?: Tag[TagMeta.PK];
};

const generateDeployedMessageForExisting = (count: number) =>
  count === 1
    ? `There is ${count} deployed machine with this tag. The new kernel options will not be applied to this machine until it is redeployed.`
    : `There are ${count} deployed machines with this tag. The new kernel options will not be applied to these machines until they are redeployed.`;

export const KernelOptionsField = ({
  deployedMachinesCount: suppliedDeployedMachinesCount,
  generateDeployedMessage = generateDeployedMessageForExisting,
  id,
}: Props): React.ReactElement => {
  const tag = useSelector((state: RootState) =>
    tagSelectors.getById(state, id)
  );
  const { machineCount } = useFetchMachineCount(
    {
      status: FetchNodeStatus.DEPLOYED,
      ...(tag?.id ? { tags: [tag.name] } : {}),
    },
    { isEnabled: !!tag?.id }
  );
  const deployedCount = suppliedDeployedMachinesCount ?? machineCount;
  const { values } = useFormikContext<CreateParams | UpdateParams>();
  const changedExistingOptions =
    isId(id) && values.kernel_opts !== tag?.kernel_opts;
  const setNewOptions = !isId(id) && values.kernel_opts;
  const hasChangedOptions = changedExistingOptions || setNewOptions;

  return (
    <FormikField
      caution={
        deployedCount > 0 && hasChangedOptions
          ? generateDeployedMessage(deployedCount)
          : null
      }
      className="p-text--code"
      component={Textarea}
      help={
        <>
          Kernel options are appended to the kernel command line during booting
          while machines are commissioning or deploying.{" "}
          <ExternalLink to={docsUrls.tagsKernelOptions}>
            Read more about kernel options in tag management
          </ExternalLink>
          .
        </>
      }
      label={Label.KernelOptions}
      name="kernel_opts"
      placeholder="e.g. nomodeset console=tty0 console=ttys0,115200n8 amd_iommu=on kvm-amd.nested=1"
    />
  );
};

export default KernelOptionsField;
