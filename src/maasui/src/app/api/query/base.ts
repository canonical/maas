import { useEffect, useCallback, useContext } from "react";

import { usePrevious } from "@canonical/react-components";
import type { UseQueryOptions } from "@tanstack/react-query";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSelector } from "react-redux";

import {
  listUserSshkeysQueryKey,
  listZonesWithStatisticsQueryKey,
} from "@/app/apiclient/@tanstack/react-query.gen";
import { WebSocketContext } from "@/app/base/websocket-context";
import statusSelectors from "@/app/store/status/selectors";
import type { WebSocketEndpointModel } from "@/websocket-client";
import { WebSocketMessageType } from "@/websocket-client";

const wsToQueryKeyMapping: Partial<Record<WebSocketEndpointModel, unknown>> = {
  zone: listZonesWithStatisticsQueryKey(),
  sshkey: listUserSshkeysQueryKey(),
};

/**
 * Provides a hook to subscribe to NOTIFY messages from the websocket.
 *
 * @returns An object with a subscribe function that takes a callback to run when a NOTIFY message is received.
 */
export const useWebSocket = () => {
  const websocketClient = useContext(WebSocketContext);

  if (!websocketClient) {
    throw new Error("useWebSocket must be used within a WebSocketProvider");
  }

  // Listen for NOTIFY messages and run a callback when received
  const subscribe = useCallback(
    (callback: ({ name }: { name: WebSocketEndpointModel }) => void) => {
      if (!websocketClient.rws) return;

      const messageHandler = (messageEvent: MessageEvent) => {
        const data = JSON.parse(messageEvent.data);
        // if we get a NOTIFY, run the provided callback
        if (data.type === WebSocketMessageType.NOTIFY) callback(data);
      };
      // add an event listener for NOTIFY messages
      websocketClient.rws.addEventListener("message", messageHandler);

      // this is a function to remove that event listener, it gets called in a cleanup effect down below.
      return () =>
        websocketClient.rws?.removeEventListener("message", messageHandler);
    },
    [websocketClient]
  );

  return { subscribe };
};

/**
 * A function to run a query which invalidates the query cache when a
 * websocket message is received, or when the websocket reconnects.
 *
 * @template TQueryFnData The type of the data which the query function will return
 * @template TError The type of error the query function might throw
 * @template TData The type of query data
 * @param options The options for useQuery
 * @returns The return value of useQuery
 */
export const useWebsocketAwareQuery = <
  TQueryFnData = unknown,
  TError = unknown,
  TData = TQueryFnData,
>(
  options?: UseQueryOptions<TQueryFnData, TError, TData>
) => {
  const queryClient = useQueryClient();
  const connectedCount = useSelector(statusSelectors.connectedCount);
  const { subscribe } = useWebSocket();

  const previousConnectedCount = usePrevious(connectedCount);

  useEffect(() => {
    (async () => {
      if (connectedCount !== previousConnectedCount) {
        await queryClient.invalidateQueries({ queryKey: options?.queryKey });
      }
    })();
  }, [connectedCount, previousConnectedCount, queryClient, options]);

  useEffect(() => {
    return subscribe(
      async ({ name: model }: { name: WebSocketEndpointModel }) => {
        // This mapped key is the key for the websocket notifications
        // TODO: replace with a function call to deduce the key/condition using the parameters
        const mappedKey = wsToQueryKeyMapping[model];
        const modelQueryKey = options?.queryKey[0];

        if (mappedKey && mappedKey === modelQueryKey) {
          await queryClient.invalidateQueries({ queryKey: options?.queryKey });
        }
      }
    );
  }, [queryClient, subscribe, options]);

  return useQuery<TQueryFnData, TError, TData>(options!);
};
