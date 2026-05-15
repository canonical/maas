import { pages } from "../../constants";
import { generateMAASURL } from "../utils";

pages.forEach(({ heading, headingLevel, url }) => {
  it(
    `"${heading}" page has no detectable accessibility violations on load`,
    { retries: 1 },
    () => {
      if (url === "/intro/user") {
        cy.login({ shouldSkipIntro: false });
      } else if (url !== "/login") {
        cy.login();
      }
      const pageUrl = generateMAASURL(url);

      cy.visit(pageUrl);
      cy.waitForPageToLoad();
      cy.findByRole("heading", {
        level: headingLevel || 1,
        name: new RegExp(heading, "i"),
      });

      cy.testA11y({ url, title: heading });
    }
  );
});
