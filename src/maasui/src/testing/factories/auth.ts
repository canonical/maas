import Chance from "chance";
import { Factory } from "fishery";
import {
  adjectives,
  animals,
  colors,
  countries,
  names,
  starWars,
  uniqueNamesGenerator,
} from "unique-names-generator";

import type { OAuthProviderResponse } from "@/app/apiclient";

export const oAuthProviderFactory = Factory.define<OAuthProviderResponse>(
  ({ sequence }) => {
    const chance = new Chance(`maas-${sequence}`);
    const name = uniqueNamesGenerator({
      dictionaries: [["Canonical IdP", "Google", "Auth0"]],
      length: 1,
      seed: sequence,
    });

    return {
      id: sequence,
      name,
      client_id: chance.guid(),
      client_secret: chance.guid(),
      issuer_url: chance.url(),
      redirect_uri: chance.url(),
      scopes: uniqueNamesGenerator({
        dictionaries: [adjectives, animals, starWars, colors, countries, names],
        length: chance.integer({ min: 1, max: 6 }),
        separator: ",",
        seed: sequence,
      }),
      token_type: "JWT",
      enabled: true,
      metadata: {
        authorization_endpoint: chance.url() + "/authorize",
        token_endpoint: chance.url() + "/token",
        userinfo_endpoint: chance.url() + "/userinfo",
        jwks_uri: chance.url() + "/jwks",
      },
    };
  }
);
