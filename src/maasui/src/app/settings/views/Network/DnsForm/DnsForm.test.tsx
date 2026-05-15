import DnsForm from "./DnsForm";

import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { configurationsResolvers } from "@/testing/resolvers/configurations";
import {
  screen,
  setupMockServer,
  mockIsPending,
  renderWithProviders,
  waitForLoading,
  userEvent,
  waitFor,
} from "@/testing/utils";

const configItems = [
  {
    name: ConfigNames.DNSSEC_VALIDATION,
    value: "auto",
    choices: [
      ["auto", "Automatic (use default root key)"],
      ["yes", "Yes (manually configured root key)"],
      ["no", "No (Disable DNSSEC; useful when upstream DNS is misconfigured)"],
    ],
  },
  { name: ConfigNames.DNS_TRUSTED_ACL, value: "" },
  { name: ConfigNames.UPSTREAM_DNS, value: "" },
];
const mockServer = setupMockServer(
  configurationsResolvers.listConfigurations.handler({ items: configItems }),
  configurationsResolvers.setBulkConfigurations.handler()
);

describe("DnsForm", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        loaded: true,
        items: [
          {
            name: ConfigNames.DNSSEC_VALIDATION,
            value: "auto",
            choices: [
              ["auto", "Automatic (use default root key)"],
              ["yes", "Yes (manually configured root key)"],
              [
                "no",
                "No (Disable DNSSEC; useful when upstream DNS is misconfigured)",
              ],
            ],
          },
        ],
      }),
    });
  });
  it("renders the dns form", async () => {
    renderWithProviders(<DnsForm />, { state });
    await waitForLoading();
    expect(
      screen.getByRole("textbox", {
        name: "Upstream DNS used to resolve domains not managed by this MAAS (space-separated IP addresses)",
      })
    ).toHaveValue("");
    const combo = screen.getByRole("combobox", {
      name: "Enable DNSSEC validation of upstream zones",
    });
    expect(combo).toHaveValue("auto");
    expect(
      screen.getByRole("textbox", {
        name: "List of external networks (not previously known), that will be allowed to use MAAS for DNS resolution",
      })
    ).toHaveValue("");
  });
  it("updates the DNS config on save", async () => {
    renderWithProviders(<DnsForm />, { state });
    await waitForLoading();
    const upstream_dns_input = screen.getByRole("textbox", {
      name: "Upstream DNS used to resolve domains not managed by this MAAS (space-separated IP addresses)",
    });

    await userEvent.type(upstream_dns_input, "0.0.0.0");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(configurationsResolvers.setBulkConfigurations.resolved).toBe(true);
    });
  });

  it("displays a spinner if config is loading", () => {
    mockIsPending();
    renderWithProviders(<DnsForm />, { state });

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });
  it("shows an error message when fetching configurations fails", async () => {
    mockServer.use(
      configurationsResolvers.listConfigurations.error({
        code: 500,
        message: "Failed to fetch configurations",
      })
    );

    renderWithProviders(<DnsForm />, { state });

    await waitFor(() => {
      expect(
        screen.getByText("Error while fetching network configurations")
      ).toBeInTheDocument();
    });
  });
  it("shows an error message when saving configurations fails", async () => {
    mockServer.use(
      configurationsResolvers.listConfigurations.handler({
        items: configItems,
      }),
      configurationsResolvers.setBulkConfigurations.error({
        code: 500,
        message: "Failed to save configurations",
      })
    );

    renderWithProviders(<DnsForm />, { state });
    await waitForLoading();
    const upstream_dns_input = screen.getByRole("textbox", {
      name: "Upstream DNS used to resolve domains not managed by this MAAS (space-separated IP addresses)",
    });

    await userEvent.type(upstream_dns_input, "0.0.0.0");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(
        screen.getByText("Failed to save configurations")
      ).toBeInTheDocument();
    });
  });
});
