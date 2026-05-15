import { actions } from "./slice";
import { RecordType } from "./types";

import * as factory from "@/testing/factories";

describe("domain actions", () => {
  it("creates an action for fetching domains", () => {
    expect(actions.fetch()).toEqual({
      type: "domain/fetch",
      meta: {
        model: "domain",
        method: "list",
      },
      payload: null,
    });
  });

  it("creates an action for creating domains", () => {
    expect(actions.create({ name: "new domain" })).toEqual({
      type: "domain/create",
      meta: {
        model: "domain",
        method: "create",
      },
      payload: { params: { name: "new domain" } },
    });
  });

  it("creates an action for updating domains", () => {
    expect(actions.update({ id: 1, name: "updated domain" })).toEqual({
      type: "domain/update",
      meta: {
        model: "domain",
        method: "update",
      },
      payload: { params: { id: 1, name: "updated domain" } },
    });
  });

  it("creates an action for getting a domain details", () => {
    expect(actions.get(1)).toEqual({
      type: "domain/get",
      meta: {
        model: "domain",
        method: "get",
      },
      payload: {
        params: {
          id: 1,
        },
      },
    });
  });

  it("creates an action for setting a default domain", () => {
    expect(actions.setDefault(1)).toEqual({
      type: "domain/setDefault",
      meta: {
        model: "domain",
        method: "set_default",
      },
      payload: {
        params: {
          domain: 1,
        },
      },
    });
  });

  it("can create an action for setting an active domain", () => {
    expect(actions.setActive(1)).toEqual({
      type: "domain/setActive",
      meta: {
        model: "domain",
        method: "set_active",
      },
      payload: {
        params: {
          id: 1,
        },
      },
    });
  });

  it("creates an action for creating a new DNSData record", () => {
    expect(
      actions.createDNSData({
        domain: 1,
        name: "name",
        rrtype: RecordType.TXT,
        rrdata: "Some data",
        ttl: 42,
      })
    ).toEqual({
      type: "domain/createDNSData",
      meta: {
        model: "domain",
        method: "create_dnsdata",
      },
      payload: {
        params: {
          domain: 1,
          name: "name",
          rrtype: RecordType.TXT,
          rrdata: "Some data",
          ttl: 42,
        },
      },
    });
  });

  it("creates an action for creating a new address record", () => {
    expect(
      actions.createAddressRecord({
        domain: 1,
        name: "name",
        ip_addresses: ["127.0.0.1"],
        address_ttl: null,
      })
    ).toEqual({
      type: "domain/createAddressRecord",
      meta: {
        model: "domain",
        method: "create_address_record",
      },
      payload: {
        params: {
          domain: 1,
          name: "name",
          ip_addresses: ["127.0.0.1"],
          address_ttl: null,
        },
      },
    });
    expect(
      actions.createAddressRecord({
        domain: 1,
        name: "name",
        ip_addresses: ["127.0.0.1", "0.0.0.0", "8.0.0.8"],
        address_ttl: 42,
      })
    ).toEqual({
      type: "domain/createAddressRecord",
      meta: {
        model: "domain",
        method: "create_address_record",
      },
      payload: {
        params: {
          domain: 1,
          name: "name",
          ip_addresses: ["127.0.0.1", "0.0.0.0", "8.0.0.8"],
          address_ttl: 42,
        },
      },
    });
  });

  it("creates an action for updating an address record", () => {
    expect(
      actions.updateAddressRecord({
        address_ttl: 1,
        domain: 2,
        ip_addresses: ["192.168.1.1"],
        name: "name",
        previous_name: "previous-name",
        previous_rrdata: "previous-rrdata",
      })
    ).toEqual({
      type: "domain/updateAddressRecord",
      meta: {
        model: "domain",
        method: "update_address_record",
      },
      payload: {
        params: {
          address_ttl: 1,
          domain: 2,
          ip_addresses: ["192.168.1.1"],
          name: "name",
          previous_name: "previous-name",
          previous_rrdata: "previous-rrdata",
        },
      },
    });
  });

  it("creates an action for updating DNS data", () => {
    expect(
      actions.updateDNSData({
        dnsdata_id: 1,
        dnsresource_id: 2,
        domain: 3,
        rrdata: "rrdata",
        rrtype: RecordType.TXT,
        ttl: 4,
      })
    ).toEqual({
      type: "domain/updateDNSData",
      meta: {
        model: "domain",
        method: "update_dnsdata",
      },
      payload: {
        params: {
          dnsdata_id: 1,
          dnsresource_id: 2,
          domain: 3,
          rrdata: "rrdata",
          rrtype: RecordType.TXT,
          ttl: 4,
        },
      },
    });
  });

  it("creates an action for updating a DNS resource", () => {
    expect(
      actions.updateDNSResource({
        dnsresource_id: 1,
        domain: 2,
        name: "new-name",
      })
    ).toEqual({
      type: "domain/updateDNSResource",
      meta: {
        model: "domain",
        method: "update_dnsresource",
      },
      payload: {
        params: {
          dnsresource_id: 1,
          domain: 2,
          name: "new-name",
        },
      },
    });
  });

  it("creates an action for updating a domain record", () => {
    const resource = factory.domainResource();
    expect(
      actions.updateRecord({
        domain: 1,
        name: "new-name",
        rrset: resource,
        rrdata: "new-rrdata",
        ttl: 2,
      })
    ).toEqual({
      type: "domain/updateRecord",
      payload: {
        params: {
          domain: 1,
          name: "new-name",
          rrset: resource,
          rrdata: "new-rrdata",
          ttl: 2,
        },
      },
    });
  });

  it("creates an action for deleting an address record", () => {
    expect(
      actions.deleteAddressRecord({
        dnsresource_id: 1,
        domain: 2,
        rrdata: "192.168.1.1",
      })
    ).toEqual({
      type: "domain/deleteAddressRecord",
      meta: {
        model: "domain",
        method: "delete_address_record",
      },
      payload: {
        params: {
          dnsresource_id: 1,
          domain: 2,
          rrdata: "192.168.1.1",
        },
      },
    });
  });

  it("creates an action for deleting DNS data", () => {
    expect(
      actions.deleteDNSData({
        dnsdata_id: 1,
        domain: 2,
      })
    ).toEqual({
      type: "domain/deleteDNSData",
      meta: {
        model: "domain",
        method: "delete_dnsdata",
      },
      payload: {
        params: {
          dnsdata_id: 1,
          domain: 2,
        },
      },
    });
  });

  it("creates an action for deleting a DNS resource", () => {
    expect(
      actions.deleteDNSResource({
        dnsresource_id: 1,
        domain: 2,
      })
    ).toEqual({
      type: "domain/deleteDNSResource",
      meta: {
        model: "domain",
        method: "delete_dnsresource",
      },
      payload: {
        params: {
          dnsresource_id: 1,
          domain: 2,
        },
      },
    });
  });

  it("creates an action for deleting a domain record", () => {
    const resource = factory.domainResource();
    expect(
      actions.deleteRecord({
        deleteResource: true,
        domain: 1,
        rrset: resource,
      })
    ).toEqual({
      type: "domain/deleteRecord",
      payload: {
        params: {
          deleteResource: true,
          domain: 1,
          rrset: resource,
        },
      },
    });
  });
});
