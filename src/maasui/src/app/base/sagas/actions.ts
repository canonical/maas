import type { PayloadAction } from "@reduxjs/toolkit";
import type { SagaGenerator } from "typed-redux-saga";
import { call } from "typed-redux-saga";

import type {
  WebSocketAction,
  WebSocketActionParams,
  WebSocketClient,
  WebSocketResponseResult,
} from "../../../websocket-client";

import { domainActions } from "@/app/store/domain";
import type {
  DeleteRecordParams,
  UpdateRecordParams,
} from "@/app/store/domain/types";
import { isAddressRecord } from "@/app/store/domain/utils";

export type NextActionCreator<R = unknown> = (
  result: WebSocketResponseResult<R>["result"]
) => WebSocketAction;

type SendMessage<R = unknown> = (
  socketClient: WebSocketClient,
  action: WebSocketAction,
  nextActionCreators?: NextActionCreator<R>[]
) => void;

export type MessageHandler<P = WebSocketActionParams> = {
  action: string;
  method: (
    socketClient: WebSocketClient,
    sendMessage: SendMessage,
    action: WebSocketAction<P>
  ) => void;
};

/**
 * Generate action to call after the initial DNS resource update action is
 * complete.
 * @param params - The params for the domain/updateRecord action.
 * @returns The next action to call.
 */
export const generateNextUpdateRecordAction = (
  params: UpdateRecordParams
): (() => WebSocketAction)[] => {
  const { domain, name, rrset } = params;
  if (!isAddressRecord(rrset.rrtype) && name !== rrset.name) {
    // The update_dnsdata method does not update the record's name, so if it's
    // been changed we also need to use the update_dnsresource method.
    return [
      () =>
        domainActions.updateDNSResource({
          dnsresource_id: rrset.dnsresource_id,
          domain,
          name,
        }),
    ];
  }
  return [];
};

/**
 * Handle updating a domain's DNS resource, then updating the DNS data.
 * @param socketClient - The websocket client instance.
 * @param sendMessage - The saga that handles sending websocket messages.
 * @param action - The redux action with updated record data.
 */
export function* updateDomainRecord(
  socketClient: WebSocketClient,
  sendMessage: SendMessage,
  { payload }: PayloadAction<{ params: UpdateRecordParams }>
): SagaGenerator<void> {
  const { domain, name, rrdata, rrset, ttl } = payload.params;
  const shouldUpdateAddressRecord = rrset.rrdata !== rrdata;
  const addressRecordAction = shouldUpdateAddressRecord
    ? domainActions.updateAddressRecord({
        address_ttl: ttl,
        domain,
        ip_addresses: rrdata?.split(",").map((ip) => ip.trim()) || [],
        name,
        previous_name: rrset.name,
        previous_rrdata: rrset.rrdata,
      })
    : domainActions.updateDNSResource({
        dnsresource_id: rrset.dnsresource_id,
        domain,
        name,
      });
  const initialAction = isAddressRecord(rrset.rrtype)
    ? addressRecordAction
    : domainActions.updateDNSData({
        dnsdata_id: rrset.dnsdata_id,
        dnsresource_id: rrset.dnsresource_id,
        domain,
        rrdata,
        ttl,
      });
  const nextAction = yield* call(
    generateNextUpdateRecordAction,
    payload.params
  );
  yield* call(sendMessage, socketClient, initialAction, nextAction);
}

/**
 * Generate action to call after the initial DNS resource delete action is
 * complete.
 * @param params - The params for the domain/deleteRecord action.
 * @returns The next action to call.
 */
export const generateNextDeleteRecordAction = (
  params: DeleteRecordParams
): (() => WebSocketAction)[] => {
  const { deleteResource, domain, rrset } = params;
  if (deleteResource) {
    // If the record is the last record of a particular DNS resource we also
    // dispatch an action to delete that DNS resource.
    return [
      () =>
        domainActions.deleteDNSResource({
          dnsresource_id: rrset.dnsresource_id,
          domain: domain,
        }),
    ];
  }
  return [];
};

/**
 * Handle deleting a domain record depending on whether it's an address record
 * and whether the underlying DNS resource should also be deleted.
 * @param socketClient - The websocket client instance.
 * @param sendMessage - The saga that handles sending websocket messages.
 * @param action - The redux action for deleting a domain record.
 */
export function* deleteDomainRecord(
  socketClient: WebSocketClient,
  sendMessage: SendMessage,
  { payload }: PayloadAction<{ params: DeleteRecordParams } | null>
): SagaGenerator<void> {
  if (payload?.params) {
    const { domain, rrset } = payload?.params;
    const initialAction = isAddressRecord(rrset.rrtype)
      ? domainActions.deleteAddressRecord({
          dnsresource_id: rrset.dnsresource_id,
          domain,
          rrdata: rrset.rrdata,
        })
      : domainActions.deleteDNSData({
          dnsdata_id: rrset.dnsdata_id,
          domain,
        });
    const nextAction = yield* call(
      generateNextDeleteRecordAction,
      payload.params
    );
    yield* call(sendMessage, socketClient, initialAction, nextAction);
  }
}

const deleteRecordHandler: MessageHandler<DeleteRecordParams> = {
  action: "domain/deleteRecord",
  method: deleteDomainRecord,
};

const updateDomainRecordHandler = {
  action: "domain/updateRecord",
  method: updateDomainRecord,
};

// Sagas to be handled by the websocket channel.
const handlers = [deleteRecordHandler, updateDomainRecordHandler];

export default handlers;
