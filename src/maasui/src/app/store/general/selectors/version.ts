/**
 * Selector for the MAAS version.
 */

import { createSelector } from "@reduxjs/toolkit";

import { generateGeneralSelector } from "./utils";

const generalSelectors = generateGeneralSelector<"version">("version");

const minor = createSelector([generalSelectors.get], (data) => {
  const splitVersion = data.split(".");
  if (splitVersion[0] && splitVersion[1]) {
    return `${splitVersion[0]}.${splitVersion[1]}`;
  }
  return "";
});

const version = {
  ...generalSelectors,
  minor,
};

export default version;
