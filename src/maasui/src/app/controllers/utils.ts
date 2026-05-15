import type { Controller } from "@/app/store/controller/types";

export const getProcessingCount = (
  selectedControllers: Controller[],
  processingControllers: Controller[]
) => {
  return processingControllers.reduce<number>((count, processingController) => {
    const controllerInSelection = selectedControllers.some(
      (controller) => controller.system_id === processingController.system_id
    );
    return controllerInSelection ? count + 1 : count;
  }, 0);
};
