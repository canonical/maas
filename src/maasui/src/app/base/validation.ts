import * as Yup from "yup";

/**
 * Validate domain name e.g. "www.example.com"
 * XXX This should be updated as it currently allows e.g. "www.example.com."
 * https://github.com/canonical/maas-ui/issues/2755
 */
export const DOMAIN_NAME_REGEX = /^([a-z\d]|[a-z\d][a-z\d-.]*[a-z\d])*$/i;

/**
 * Validate IPv4 address e.g 192.168.1.1
 */
export const IPV4_REGEX =
  /\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)(?::\d{0,4})?\b/;

/**
 * Validate MAC address e.g 78:9a:bc:de:f0
 */
export const MAC_ADDRESS_REGEX = /^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$/;

/**
 * Validate range string e.g 0-2, 4, 6-7
 */
export const RANGE_REGEX = /^\d{1,3}(-\d{1,3})?(,\s*(\d{1,3}(-\d{1,3})?))*$/;

/**
 * Validate tag name string (only alphanumeric, dash or underscore)
 */
export const TAG_NAME_REGEX = /^[a-zA-Z0-9_-]+$/;

export enum HostnameValidationLabel {
  LengthError = "Hostname must be 63 characters or less.",
  CharactersError = "Hostname must only contain letters, numbers and hyphens.",
  DashStartError = "Hostname must not start wth a hyphen.",
  DashEndError = "Hostname must not end wth a hyphen.",
}

export const hostnameValidation = Yup.string()
  .max(63, HostnameValidationLabel.LengthError)
  // Validate host name only contains alphanumeric or dash.
  .matches(/^[a-zA-Z0-9-]*$/, HostnameValidationLabel.CharactersError)
  // Validate host name does not start with a dash.
  .matches(/^[a-zA-Z0-9]/, HostnameValidationLabel.DashStartError)
  // Validate host name does not end with a dash.
  .matches(/[a-zA-Z0-9]$/, HostnameValidationLabel.DashEndError);

export const UrlSchemaError = "Must be a valid URL.";

/**
 * Validate a URL e.g. "http://example.com"
 * If a URL is required, chain with the Yup .required() method
 * The URL value is optional
 */
export const UrlSchema = Yup.string().test({
  name: "url",
  test: (value) => {
    if (!value) {
      return true;
    }
    try {
      const valid = new URL(value);
      return !!valid;
    } catch {
      return false;
    }
  },
  message: UrlSchemaError,
});
