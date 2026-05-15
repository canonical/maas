import bondOptions from "./bondOptions";

import {
  BondLacpRate,
  BondMode,
  BondXmitHashPolicy,
} from "@/app/store/general/types";
import type {
  BondLacpRateOptions,
  BondModeOptions,
  BondXmitHashPolicyOptions,
} from "@/app/store/general/types";
import * as factory from "@/testing/factories";

const lacpRates: BondLacpRateOptions = [
  [BondLacpRate.FAST, BondLacpRate.FAST],
  [BondLacpRate.SLOW, BondLacpRate.SLOW],
];

const modes: BondModeOptions = [
  [BondMode.BALANCE_RR, BondMode.BALANCE_RR],
  [BondMode.ACTIVE_BACKUP, BondMode.ACTIVE_BACKUP],
  [BondMode.BALANCE_XOR, BondMode.BALANCE_XOR],
  [BondMode.BROADCAST, BondMode.BROADCAST],
  [BondMode.LINK_AGGREGATION, BondMode.LINK_AGGREGATION],
  [BondMode.BALANCE_TLB, BondMode.BALANCE_TLB],
  [BondMode.BALANCE_ALB, BondMode.BALANCE_ALB],
];

const xmitHashPolicies: BondXmitHashPolicyOptions = [
  [BondXmitHashPolicy.LAYER2, BondXmitHashPolicy.LAYER2],
  [BondXmitHashPolicy.LAYER2_3, BondXmitHashPolicy.LAYER2_3],
  [BondXmitHashPolicy.LAYER3_4, BondXmitHashPolicy.LAYER3_4],
  [BondXmitHashPolicy.ENCAP2_3, BondXmitHashPolicy.ENCAP2_3],
  [BondXmitHashPolicy.ENCAP3_4, BondXmitHashPolicy.ENCAP3_4],
];

describe("bondOptions selectors", () => {
  describe("get", () => {
    it("returns bond options", () => {
      const data = {
        lacp_rates: lacpRates,
        modes,
        xmit_hash_policies: xmitHashPolicies,
      };
      const state = factory.rootState({
        general: factory.generalState({
          bondOptions: factory.bondOptionsState({
            data,
          }),
        }),
      });
      expect(bondOptions.get(state)).toStrictEqual(data);
    });
  });

  describe("loading", () => {
    it("returns bond options loading state", () => {
      const loading = true;
      const state = factory.rootState({
        general: factory.generalState({
          bondOptions: factory.bondOptionsState({
            loading,
          }),
        }),
      });
      expect(bondOptions.loading(state)).toStrictEqual(loading);
    });
  });

  describe("loaded", () => {
    it("returns bond options loaded state", () => {
      const loaded = true;
      const state = factory.rootState({
        general: factory.generalState({
          bondOptions: factory.bondOptionsState({
            loaded,
          }),
        }),
      });
      expect(bondOptions.loaded(state)).toStrictEqual(loaded);
    });
  });

  describe("errors", () => {
    it("returns bond options errors state", () => {
      const errors = "Cannot fetch bondOptions.";
      const state = factory.rootState({
        general: factory.generalState({
          bondOptions: factory.bondOptionsState({
            errors,
          }),
        }),
      });
      expect(bondOptions.errors(state)).toStrictEqual(errors);
    });
  });

  describe("lacpRates", () => {
    it("returns LACP rates with the nested arrays removed", () => {
      const state = factory.rootState({
        general: factory.generalState({
          bondOptions: factory.bondOptionsState({
            data: factory.bondOptions({
              lacp_rates: lacpRates,
            }),
          }),
        }),
      });
      expect(bondOptions.lacpRates(state)).toStrictEqual(["fast", "slow"]);
    });
  });

  describe("modes", () => {
    it("returns modes with the nested arrays removed", () => {
      const state = factory.rootState({
        general: factory.generalState({
          bondOptions: factory.bondOptionsState({
            data: factory.bondOptions({
              modes,
            }),
          }),
        }),
      });
      expect(bondOptions.modes(state)).toStrictEqual([
        "balance-rr",
        "active-backup",
        "balance-xor",
        "broadcast",
        "802.3ad",
        "balance-tlb",
        "balance-alb",
      ]);
    });
  });

  describe("xmitHashPolicies", () => {
    it("returns XMIT hash policies with the nested arrays removed", () => {
      const state = factory.rootState({
        general: factory.generalState({
          bondOptions: factory.bondOptionsState({
            data: factory.bondOptions({
              xmit_hash_policies: xmitHashPolicies,
            }),
          }),
        }),
      });
      expect(bondOptions.xmitHashPolicies(state)).toStrictEqual([
        "layer2",
        "layer2+3",
        "layer3+4",
        "encap2+3",
        "encap3+4",
      ]);
    });
  });
});
