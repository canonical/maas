import { createSlice } from "@reduxjs/toolkit";
import type { PayloadAction } from "@reduxjs/toolkit";

import { DomainMeta } from "./types";
import type {
  CreateAddressRecordParams,
  CreateDNSDataParams,
  CreateParams,
  DeleteAddressRecordParams,
  DeleteDNSDataParams,
  DeleteDNSResourceParams,
  DeleteRecordParams,
  Domain,
  DomainState,
  SetDefaultErrors,
  UpdateAddressRecordParams,
  UpdateDNSDataParams,
  UpdateDNSResourceParams,
  UpdateParams,
  UpdateRecordParams,
} from "./types";

import type { APIError } from "@/app/base/types";
import {
  generateCommonReducers,
  generateGetReducers,
  genericInitialState,
} from "@/app/store/utils/slice";

const domainSlice = createSlice({
  name: DomainMeta.MODEL,
  initialState: {
    ...genericInitialState,
    active: null,
  } as DomainState,
  reducers: {
    ...generateCommonReducers<
      DomainState,
      DomainMeta.PK,
      CreateParams,
      UpdateParams
    >({
      modelName: DomainMeta.MODEL,
      primaryKey: DomainMeta.PK,
    }),
    ...generateGetReducers<DomainState, Domain, DomainMeta.PK>({
      modelName: DomainMeta.MODEL,
      primaryKey: DomainMeta.PK,
    }),
    setDefault: {
      prepare: (id: Domain[DomainMeta.PK]) => ({
        meta: {
          model: DomainMeta.MODEL,
          method: "set_default",
        },
        payload: {
          params: { domain: id },
        },
      }),
      reducer: () => {},
    },
    setDefaultStart: (state: DomainState) => {
      state.saving = true;
      state.saved = false;
    },
    setDefaultError: (
      state: DomainState,
      action: PayloadAction<SetDefaultErrors>
    ) => {
      state.saving = false;
      state.errors = action.payload;
    },
    setDefaultSuccess: (state: DomainState, action: PayloadAction<Domain>) => {
      state.saving = false;
      state.saved = true;
      state.errors = null;

      // update the default domain in the redux store
      state.items.forEach((domain) => {
        if (domain.id === action.payload.id) {
          domain.is_default = true;
        } else {
          domain.is_default = false;
        }
      });
    },
    setActive: {
      prepare: (id: Domain[DomainMeta.PK] | null) => ({
        meta: {
          model: DomainMeta.MODEL,
          method: "set_active",
        },
        payload: {
          // Server unsets active domain if primary key (id) is not sent.
          params: id === null ? null : { id },
        },
      }),
      reducer: () => {},
    },
    setActiveError: (
      state: DomainState,
      action: PayloadAction<DomainState["errors"]>
    ) => {
      state.active = null;
      state.errors = action.payload;
    },
    setActiveSuccess: (
      state: DomainState,
      action: PayloadAction<Domain | null>
    ) => {
      state.active = action.payload?.id || null;
    },
    createAddressRecord: {
      prepare: (params: CreateAddressRecordParams) => ({
        meta: {
          model: DomainMeta.MODEL,
          method: "create_address_record",
        },
        payload: {
          params,
        },
      }),
      reducer: () => {},
    },
    createAddressRecordStart: (state: DomainState) => {
      state.saving = true;
      state.saved = false;
    },
    createAddressRecordError: (
      state: DomainState,
      action: PayloadAction<APIError>
    ) => {
      state.saving = false;
      state.errors = action.payload;
    },
    createAddressRecordSuccess: (state: DomainState) => {
      state.saving = false;
      state.saved = true;
      state.errors = null;
    },
    createDNSData: {
      prepare: (params: CreateDNSDataParams) => ({
        meta: {
          model: DomainMeta.MODEL,
          method: "create_dnsdata",
        },
        payload: {
          params,
        },
      }),
      reducer: () => {},
    },
    createDNSDataStart: (state: DomainState) => {
      state.saving = true;
      state.saved = false;
    },
    createDNSDataError: (
      state: DomainState,
      action: PayloadAction<APIError>
    ) => {
      state.saving = false;
      state.errors = action.payload;
    },
    createDNSDataSuccess: (state: DomainState) => {
      state.saving = false;
      state.saved = true;
      state.errors = null;
    },
    deleteAddressRecord: {
      prepare: (params: DeleteAddressRecordParams) => {
        return {
          meta: {
            model: DomainMeta.MODEL,
            method: "delete_address_record",
          },
          payload: {
            params: params,
          },
        } as const;
      },
      reducer: () => {},
    },
    deleteAddressRecordStart: (state: DomainState) => {
      state.saving = true;
      state.saved = false;
    },
    deleteAddressRecordError: (
      state: DomainState,
      action: PayloadAction<APIError>
    ) => {
      state.saving = false;
      state.errors = action.payload;
    },
    deleteAddressRecordSuccess: (state: DomainState) => {
      state.saving = false;
      state.saved = true;
      state.errors = null;
    },
    deleteDNSData: {
      prepare: (params: DeleteDNSDataParams) => {
        return {
          meta: {
            model: DomainMeta.MODEL,
            method: "delete_dnsdata",
          },
          payload: {
            params,
          },
        } as const;
      },
      reducer: () => {},
    },
    deleteDNSDataStart: (state: DomainState) => {
      state.saving = true;
      state.saved = false;
    },
    deleteDNSDataError: (
      state: DomainState,
      action: PayloadAction<APIError>
    ) => {
      state.saving = false;
      state.errors = action.payload;
    },
    deleteDNSDataSuccess: (state: DomainState) => {
      state.saving = false;
      state.saved = true;
      state.errors = null;
    },
    deleteDNSResource: {
      prepare: (params: DeleteDNSResourceParams) => {
        return {
          meta: {
            model: DomainMeta.MODEL,
            method: "delete_dnsresource",
          },
          payload: {
            params: params,
          },
        } as const;
      },
      reducer: () => {},
    },
    deleteDNSResourceError: (
      state: DomainState,
      action: PayloadAction<APIError>
    ) => {
      state.errors = action.payload;
    },
    deleteDNSResourceSuccess: (state: DomainState) => {
      state.errors = null;
    },
    deleteRecord: {
      prepare: (params: DeleteRecordParams) => ({
        payload: {
          params,
        },
      }),
      reducer: () => {},
    },
    updateAddressRecord: {
      prepare: (params: UpdateAddressRecordParams) => {
        return {
          meta: {
            model: DomainMeta.MODEL,
            method: "update_address_record",
          },
          payload: {
            params,
          },
        } as const;
      },
      reducer: () => {},
    },
    updateAddressRecordStart: (state: DomainState) => {
      state.saving = true;
      state.saved = false;
    },
    updateAddressRecordError: (
      state: DomainState,
      action: PayloadAction<APIError>
    ) => {
      state.saving = false;
      state.errors = action.payload;
    },
    updateAddressRecordSuccess: (state: DomainState) => {
      state.saving = false;
      state.saved = true;
      state.errors = null;
    },
    updateDNSData: {
      prepare: (params: UpdateDNSDataParams) => {
        return {
          meta: {
            model: DomainMeta.MODEL,
            method: "update_dnsdata",
          },
          payload: {
            params,
          },
        } as const;
      },
      reducer: () => {},
    },
    updateDNSDataStart: (state: DomainState) => {
      state.saving = true;
      state.saved = false;
    },
    updateDNSDataError: (
      state: DomainState,
      action: PayloadAction<APIError>
    ) => {
      state.saving = false;
      state.errors = action.payload;
    },
    updateDNSDataSuccess: (state: DomainState) => {
      state.saving = false;
      state.saved = true;
      state.errors = null;
    },
    updateDNSResource: {
      prepare: (params: UpdateDNSResourceParams) => {
        return {
          meta: {
            model: DomainMeta.MODEL,
            method: "update_dnsresource",
          },
          payload: {
            params: params,
          },
        } as const;
      },
      reducer: () => {},
    },
    updateDNSResourceStart: (state: DomainState) => {
      state.saving = true;
      state.saved = false;
    },
    updateDNSResourceSuccess: (state: DomainState) => {
      state.saving = false;
      state.saved = true;
      state.errors = null;
    },
    updateDNSResourceError: (
      state: DomainState,
      action: PayloadAction<APIError>
    ) => {
      state.saving = false;
      state.errors = action.payload;
    },
    updateRecord: {
      prepare: (params: UpdateRecordParams) => ({
        payload: {
          params,
        },
      }),
      reducer: () => {},
    },
  },
});

export const { actions } = domainSlice;

export default domainSlice.reducer;
