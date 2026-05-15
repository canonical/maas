import { queryOptionsWithHeaders } from "../utils";

import { useWebsocketAwareQuery } from "./base";

import type {
  ListFabricsData,
  ListFabricsErrors,
  ListFabricsResponses,
} from "@/app/apiclient";
import { listFabrics } from "@/app/apiclient";
import { listFabricsQueryKey } from "@/app/apiclient/@tanstack/react-query.gen";
import type { Options } from "@/app/apiclient/client";

export const useFabrics = (options?: Options<ListFabricsData>) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<
      ListFabricsResponses,
      ListFabricsErrors,
      ListFabricsData
    >(options, listFabrics, listFabricsQueryKey(options))
  );
};
