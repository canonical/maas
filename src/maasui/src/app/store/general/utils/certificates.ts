import type { CertificateMetadata } from "@/app/store/general/types";

/**
 * Split a certificate name in to object and host names, where certificate names
 * come in the form "object-name@host-name" if a host exists, otherwise simply
 * "object-name".
 *
 * @param certificateName - the common name (CN) of the certificate.
 * @returns object name and host name.
 */
export const splitCertificateName = (
  certificateName: CertificateMetadata["CN"] | null
): { name: string; host: string } | null => {
  if (!certificateName) {
    return null;
  }
  const split = certificateName.split("@");
  if (split.length < 2) {
    return { name: certificateName, host: "" };
  }
  // Assume it's possible to have multiple "@"s in a CN, in which the last item
  // is the host name. e.g. the host for "machine@address@host" is "host".
  const host = split[split.length - 1];
  const name = split.slice(0, split.length - 1).join("@");
  return { name, host };
};
