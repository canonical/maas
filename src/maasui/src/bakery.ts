import { Bakery, BakeryStorage } from "@canonical/macaroon-bakery";

import { store } from "./redux-store";

import { statusActions } from "@/app/store/status";

// Initialise Macaroon Bakery singleton
const visit = (error: { Info: { VisitURL: string } }) => {
  const url = error.Info.VisitURL;
  store.dispatch(statusActions.externalLoginURL({ url }));
  window.open(url, "_blank");
};

const bakery = new Bakery({
  protocolVersion: 1,
  storage: new BakeryStorage(localStorage, {}),
  visitPage: visit,
});

export default bakery;
