import type { CommonActionFormProps } from "@/app/base/types";
import type {
  Machine,
  MachineEventErrors,
  SelectedMachines,
} from "@/app/store/machine/types";

export type MachineActionVariableProps = {
  machines?: Machine[];
  selectedMachines?: SelectedMachines | null;
  searchFilter?: string;
  selectedCount?: number | null;
  processingCount?: number;
  selectedCountLoading?: boolean;
};

export type MachineActionFormProps = MachineActionVariableProps &
  Omit<CommonActionFormProps<MachineEventErrors>, "processingCount">;

export type MachineMenuToggleHandler = (open: boolean) => void;
export type GetMachineMenuToggleHandler = (
  eventLabel: string
) => MachineMenuToggleHandler;
