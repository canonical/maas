import type { APIError } from "@/app/base/types";
import type { GeneralState } from "@/app/store/general/types";
import type { RootState } from "@/app/store/root/types";

type GeneralSelector<T extends keyof GeneralState> = {
  errors: (state: RootState) => APIError;
  get: (state: RootState) => GeneralState[T]["data"];
  loaded: (state: RootState) => boolean;
  loading: (state: RootState) => boolean;
};

export const generateGeneralSelector = <T extends keyof GeneralState>(
  name: T
): GeneralSelector<T> => {
  const get = (state: RootState) => state.general[name].data;
  const loading = (state: RootState) => state.general[name].loading;
  const loaded = (state: RootState) => state.general[name].loaded;
  const errors = (state: RootState) => state.general[name].errors;

  return {
    errors,
    get,
    loaded,
    loading,
  };
};

export default generateGeneralSelector;
