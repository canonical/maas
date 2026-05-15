import type { OAuthProviderResponse } from "@/app/apiclient";

export type SingleSignOnFormValues = Omit<
  OAuthProviderResponse,
  "enabled" | "id" | "metadata"
>;
