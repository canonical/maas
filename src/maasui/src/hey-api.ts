import type { CreateClientConfig } from "./app/apiclient/client.gen";

export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
  baseUrl: "/",
  headers: {
    cookie: document.cookie,
  },
});
