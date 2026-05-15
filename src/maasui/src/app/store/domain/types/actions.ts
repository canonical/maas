import type { Domain, DomainResource } from "./base";
import type { DomainMeta } from "./enum";

export type CreateAddressRecordParams = {
  address_ttl: DomainResource["ttl"] | null;
  domain: Domain[DomainMeta.PK];
  ip_addresses: string[];
  name: DomainResource["name"];
};

export type CreateDNSDataParams = {
  domain: Domain[DomainMeta.PK];
  name: DomainResource["name"];
  rrdata: DomainResource["rrdata"];
  rrtype: DomainResource["rrtype"];
  ttl: DomainResource["ttl"];
};

export type CreateParams = {
  authoritative?: Domain["authoritative"];
  name: Domain["name"];
  ttl?: Domain["ttl"];
};

export type DeleteAddressRecordParams = {
  dnsresource_id: DomainResource["dnsresource_id"];
  domain: Domain["id"];
  rrdata: DomainResource["rrdata"];
};

export type DeleteDNSDataParams = {
  dnsdata_id: DomainResource["dnsdata_id"];
  domain: Domain["id"];
};

export type DeleteDNSResourceParams = {
  dnsresource_id: DomainResource["dnsresource_id"];
  domain: Domain["id"];
};

export type DeleteRecordParams = {
  deleteResource: boolean;
  domain: Domain["id"];
  rrset: DomainResource;
};

export type SetDefaultErrors = string | { domain: string[] };

export type UpdateAddressRecordParams = {
  address_ttl: DomainResource["ttl"];
  domain: Domain["id"];
  ip_addresses: string[];
  name: DomainResource["name"];
  previous_name: DomainResource["name"];
  previous_rrdata: DomainResource["rrdata"];
};

export type UpdateDNSDataParams = {
  dnsdata_id: DomainResource["dnsdata_id"];
  dnsresource_id: DomainResource["dnsresource_id"];
  domain: Domain["id"];
  rrdata?: DomainResource["rrdata"];
  rrtype?: DomainResource["rrtype"];
  ttl?: DomainResource["ttl"];
};

export type UpdateDNSResourceParams = {
  dnsresource_id: DomainResource["dnsresource_id"];
  domain: Domain["id"];
  name: DomainResource["name"];
};

export type UpdateParams = {
  [DomainMeta.PK]: Domain[DomainMeta.PK];
  authoritative?: Domain["authoritative"];
  name?: Domain["name"];
  ttl?: Domain["ttl"];
};

export type UpdateRecordParams = {
  domain: Domain["id"];
  name: DomainResource["name"];
  rrdata: DomainResource["rrdata"];
  rrset: DomainResource;
  ttl: DomainResource["ttl"];
};
