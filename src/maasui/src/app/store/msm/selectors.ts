import { createSelector } from "@reduxjs/toolkit";

import type { MsmStatus } from "@/app/store/msm/types/base";
import type { RootState } from "@/app/store/root/types";

const status = (state: RootState): MsmStatus | null => state.msm.status;
const running = createSelector(status, (status) => status?.running);
const loading = (state: RootState): boolean => state.msm.loading;
const errors = (state: RootState): string | null => state.msm.errors;

const msmSelectors = {
  status,
  running,
  loading,
  errors,
};

export default msmSelectors;
