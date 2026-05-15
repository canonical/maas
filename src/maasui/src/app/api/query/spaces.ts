import { queryOptionsWithHeaders } from "../utils";

import { useWebsocketAwareQuery } from "./base";

import type {
  ListSpacesData,
  ListSpacesErrors,
  ListSpacesResponses,
  Options,
} from "@/app/apiclient";
import { listSpaces } from "@/app/apiclient";
import { listSpacesQueryKey } from "@/app/apiclient/@tanstack/react-query.gen";

export const useSpaces = (options?: Options<ListSpacesData>) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<
      ListSpacesResponses,
      ListSpacesErrors,
      ListSpacesData
    >(options, listSpaces, listSpacesQueryKey(options))
  );
};
