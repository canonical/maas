import { ValidationError } from "yup";

import {
  hostnameValidation,
  HostnameValidationLabel,
  UrlSchema,
  UrlSchemaError,
} from "./validation";

describe("hostname regex", () => {
  it("is valid if undefined", async () => {
    await expect(hostnameValidation.validate(undefined)).resolves.toBe(
      undefined
    );
  });

  it("handles valid characters", async () => {
    await expect(hostnameValidation.validate("valid-name")).resolves.toBe(
      "valid-name"
    );
  });

  it("handles invalid characters", async () => {
    await expect(
      hostnameValidation.validate("valid_name")
    ).rejects.toStrictEqual(
      new ValidationError(HostnameValidationLabel.CharactersError)
    );
  });

  it("is invalid if it starts with a dash", async () => {
    await expect(
      hostnameValidation.validate("-invalidname")
    ).rejects.toStrictEqual(
      new ValidationError(HostnameValidationLabel.DashStartError)
    );
  });

  it("is invalid if it ends with a dash", async () => {
    await expect(
      hostnameValidation.validate("invalidname-")
    ).rejects.toStrictEqual(
      new ValidationError(HostnameValidationLabel.DashEndError)
    );
  });

  it("is invalid if it is longer than 63 characters", async () => {
    await expect(
      hostnameValidation.validate(
        "invalidnamethatiswaytoolongimeanthisislongbyanystandardormeasure"
      )
    ).rejects.toStrictEqual(
      new ValidationError(HostnameValidationLabel.LengthError)
    );
  });
});

describe("UrlSchema", () => {
  it("is valid if undefined", async () => {
    await expect(UrlSchema.validate(undefined)).resolves.toBe(undefined);
  });

  it("is invalid if undefined when chained with .required()", async () => {
    await expect(
      UrlSchema.required("URL is required").validate(undefined)
    ).rejects.toStrictEqual(new ValidationError("URL is required"));
  });

  it("rejects invalid URLs", async () => {
    await expect(UrlSchema.validate("test")).rejects.toStrictEqual(
      new ValidationError(UrlSchemaError)
    );
  });

  it("allows URLs with a TLD", async () => {
    await expect(UrlSchema.validate("http://test.proxy")).resolves.toBe(
      "http://test.proxy"
    );
  });

  it("allows URLs without a TLD (e.g. test.proxy, )", async () => {
    await expect(UrlSchema.validate("localhost:300")).resolves.toBe(
      "localhost:300"
    );
  });
});
