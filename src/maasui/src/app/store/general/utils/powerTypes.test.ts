import {
  formatPowerParameters,
  generatePowerParametersSchema,
  getFieldsInScope,
  getPowerTypeFromName,
} from "./powerTypes";

import { PowerFieldScope } from "@/app/store/general/types";
import * as factory from "@/testing/factories";

describe("powerTypes utils", () => {
  describe("formatPowerParameters", () => {
    it("trims power parameters object to those relevant to power type", () => {
      const powerType = factory.powerType({
        fields: [
          factory.powerField({ name: "power_address" }),
          factory.powerField({ name: "power_pass" }),
        ],
      });
      const powerParameters = {
        power_address: "address",
        power_pass: "password",
        power_port: "8000",
      };
      expect(formatPowerParameters(powerType, powerParameters)).toStrictEqual({
        power_address: "address",
        power_pass: "password",
      });
    });

    it("can rename parameters for when adding a chassis", () => {
      const powerType = factory.powerType({
        fields: [
          factory.powerField({ name: "power_address" }),
          factory.powerField({ name: "power_pass" }),
          factory.powerField({ name: "power_port" }),
          factory.powerField({ name: "power_protocol" }),
          factory.powerField({ name: "power_token_name" }),
          factory.powerField({ name: "power_token_secret" }),
          factory.powerField({ name: "power_user" }),
          factory.powerField({ name: "power_verify_ssl" }),
        ],
      });

      const powerParameters = {
        power_address: "value1",
        power_pass: "value2",
        power_port: "value3",
        power_protocol: "value4",
        power_token_name: "value5",
        power_token_secret: "value6",
        power_user: "value7",
        power_verify_ssl: "value8",
      };
      expect(
        formatPowerParameters(powerType, powerParameters, undefined, true)
      ).toStrictEqual({
        hostname: "value1",
        password: "value2",
        port: "value3",
        protocol: "value4",
        token_name: "value5",
        token_secret: "value6",
        username: "value7",
        verify_ssl: "value8",
      });
    });

    it("can filter fields based on their scope", () => {
      const powerType = factory.powerType({
        fields: [
          factory.powerField({
            name: "power_address",
            scope: PowerFieldScope.BMC,
          }),
          factory.powerField({
            name: "power_pass",
            scope: PowerFieldScope.BMC,
          }),
          factory.powerField({ name: "power_id", scope: PowerFieldScope.NODE }),
        ],
      });

      const powerParameters = {
        power_address: "power_address",
        power_pass: "power_pass",
        power_id: "5",
      };
      expect(
        formatPowerParameters(powerType, powerParameters, [PowerFieldScope.BMC])
      ).toStrictEqual({
        power_address: "power_address",
        power_pass: "power_pass",
      });
    });
  });

  describe("generatePowerParametersSchema", () => {
    it("can generate a schema based on the power type", () => {
      const powerType = factory.powerType({
        fields: [
          factory.powerField({ name: "power_address", required: false }),
          factory.powerField({ name: "power_pass", required: true }),
        ],
      });
      const schema = generatePowerParametersSchema(powerType);
      expect("power_address" in schema).toBe(true);
      expect("power_pass" in schema).toBe(true);
    });

    it("can filter schema parameters based on the field scopes", () => {
      const powerType = factory.powerType({
        fields: [
          factory.powerField({
            name: "power_address",
            scope: PowerFieldScope.BMC,
          }),
          factory.powerField({
            name: "power_pass",
            scope: PowerFieldScope.NODE,
          }),
        ],
      });
      const schema = generatePowerParametersSchema(powerType, [
        PowerFieldScope.BMC,
      ]);
      expect("power_address" in schema).toBe(true);
      expect("power_pass" in schema).toBe(false);
    });
  });

  describe("getFieldsInScope", () => {
    it("can get a list of power fields that are in the given field scopes", () => {
      const fields = [
        factory.powerField({ scope: PowerFieldScope.BMC }),
        factory.powerField({ scope: PowerFieldScope.NODE }),
      ];
      const powerType = factory.powerType({ fields });

      expect(getFieldsInScope(powerType, [PowerFieldScope.BMC])).toStrictEqual([
        fields[0],
      ]);
      expect(getFieldsInScope(null, [PowerFieldScope.BMC])).toStrictEqual([]);
    });
  });

  describe("getPowerTypeFromName", () => {
    it("can get a power type from its name", () => {
      const powerTypes = [factory.powerType({ name: "manual" })];

      expect(getPowerTypeFromName(powerTypes, "manual")).toBe(powerTypes[0]);
      expect(getPowerTypeFromName(powerTypes, "other")).toBe(null);
    });
  });
});
