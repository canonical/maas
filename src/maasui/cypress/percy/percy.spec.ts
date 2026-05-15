import { pages } from "../constants";
import { generateMAASURL } from "../e2e/utils";

pages.forEach(({ heading, url }) => {
  it(`"Loads the ${heading}" page`, () => {
    if (url === "/intro/user") {
      cy.login({ shouldSkipIntro: false });
    } else if (url !== "/a/v3/auth/login") {
      cy.login();
    }
    const pageUrl = generateMAASURL(url);
    cy.visit(pageUrl);
    cy.waitForPageToLoad();
    cy.percySnapshot(heading);
  });
});
