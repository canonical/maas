import ResourceRecordsTable from "./ResourceRecordsTable";

import type { DomainDetails } from "@/app/store/domain/types";
import { RecordType } from "@/app/store/domain/types";
import * as factory from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  waitFor,
  within,
} from "@/testing/utils";

const mockServer = setupMockServer(
  authResolvers.getCurrentUser.handler(),
  authResolvers.getMeStatistics.handler()
);

describe("ResourceRecordsTable", () => {
  let items: DomainDetails;
  beforeEach(() => {
    items = factory.domainDetails({
      id: 3,
      name: "sample_domain",
      is_default: true,
      rrsets: [
        {
          name: "abc",
          ttl: 20,
          system_id: "132",
          user_id: null,
          dnsdata_id: 15,
          dnsresource_id: 100,
          node_type: 4,
          rrdata: "192.168.1.1",
          rrtype: RecordType.A,
        },
      ],
    });
  });

  it("renders the right columns", () => {
    renderWithProviders(<ResourceRecordsTable domain={items} id={1} />);
    ["Name", "Type", "TTL", "Data", "Actions"].forEach((column) => {
      expect(
        screen.getByRole("columnheader", {
          name: new RegExp(`^${column}`, "i"),
        })
      ).toBeInTheDocument();
    });
  });

  it("displays a message when there is no data", () => {
    items.rrsets = [];
    renderWithProviders(<ResourceRecordsTable domain={items} id={1} />);

    expect(
      screen.getByRole("cell", { name: "Domain contains no records." })
    ).toBeInTheDocument();
  });

  it("displays row data correctly", () => {
    renderWithProviders(<ResourceRecordsTable domain={items} id={1} />);

    const row = within(screen.getAllByRole("row")[1]);

    expect(row.getAllByRole("cell")[0]).toHaveTextContent("abc");
    expect(row.getAllByRole("cell")[1]).toHaveTextContent(RecordType.A);
    expect(row.getAllByRole("cell")[2]).toHaveTextContent("20");
    expect(row.getAllByRole("cell")[3]).toHaveTextContent("192.168.1.1");
  });

  it("renders a link in the name column when id is auto-generated", () => {
    items.rrsets[0].dnsresource_id = null;
    renderWithProviders(<ResourceRecordsTable domain={items} id={1} />);

    expect(
      screen.getByRole("cell", { name: "abc" }).firstChild
    ).toHaveAttribute(
      "href",
      expect.stringMatching(/^\/(machine|controller|device)\/132$/)
    );
  });

  it("disables action dropdown when id is auto-generated", async () => {
    items.rrsets[0].dnsresource_id = null;

    renderWithProviders(<ResourceRecordsTable domain={items} id={1} />);
    const dropdownBtn = screen.getByRole("button", { name: "Toggle menu" });

    await waitFor(() => {
      expect(dropdownBtn).toHaveClass("is-disabled");
    });
  });

  it("disables action dropdown when user is not a superuser", async () => {
    items.rrsets[0].dnsresource_id = 50;
    mockServer.use(
      authResolvers.getCurrentUser.handler(
        factory.user({ is_superuser: false })
      )
    );
    renderWithProviders(<ResourceRecordsTable domain={items} id={1} />);
    const dropdownBtn = screen.getByRole("button", { name: "Toggle menu" });
    await waitFor(() => {
      expect(dropdownBtn).toHaveClass("is-disabled");
    });
  });

  it("enables action dropdown only when user is a superuser and tag is not system-generated", async () => {
    mockServer.use(
      authResolvers.getCurrentUser.handler(factory.user({ is_superuser: true }))
    );
    items.rrsets[0].dnsresource_id = 100;
    renderWithProviders(<ResourceRecordsTable domain={items} id={1} />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Toggle menu" })
      ).not.toHaveClass("is-disabled");
    });
  });
});
