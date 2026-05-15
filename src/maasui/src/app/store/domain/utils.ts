import type { Domain, DomainDetails } from "./types";
import { RecordType } from "./types";

/**
 * Whether a record type is an address record.
 * @param domain - The record type to check.
 * @returns Whether the record type is an address record.
 */
export const isAddressRecord = (recordType: RecordType): boolean =>
  [RecordType.A, RecordType.AAAA].includes(recordType);

/**
 * Whether a domain has a DomainDetails type.
 * @param domain - The domain to check
 * @returns Whether the domain is DomainDetails.
 */
export const isDomainDetails = (
  domain?: Domain | null
  // Use "rrsets" as the canary as it only exists for DomainDetails.
): domain is DomainDetails => !!domain && "rrsets" in domain;
