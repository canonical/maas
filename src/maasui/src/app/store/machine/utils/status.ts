import { NodeStatusCode } from "@/app/store/types/node";

/**
 * Returns whether a a status code represents a transient status.
 * @param statusCode - the status code to check.
 * @returns whether the status code is a transient status.
 */
export const isTransientStatus = (statusCode: NodeStatusCode): boolean =>
  [
    NodeStatusCode.COMMISSIONING,
    NodeStatusCode.DEPLOYING,
    NodeStatusCode.DISK_ERASING,
    NodeStatusCode.ENTERING_RESCUE_MODE,
    NodeStatusCode.EXITING_RESCUE_MODE,
    NodeStatusCode.RELEASING,
    NodeStatusCode.TESTING,
  ].includes(statusCode);
