import { Given, Then } from "@badeball/cypress-cucumber-preprocessor";
import { routes } from "../../../constants";
import { generateMAASURL } from "../../../e2e/utils";

const escapeRegExp = (value: string) =>
  value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

Given(/^the user navigates to the (.+) page$/, (page: string) => {
  const path = routes[page];
  cy.visit(generateMAASURL(path));
  cy.waitForPageToLoad();
});

Then(/^the user is redirected to the (.+) page$/, (page: string) => {
  const path = routes[page];
  cy.visit(generateMAASURL(path));
});

Then("the pathname should equal {string}", (expectedPath: string) => {
  const expectedFullPath = generateMAASURL(expectedPath);

  if (expectedPath.includes("*")) {
    const pattern = `^${escapeRegExp(expectedFullPath).replace(/\\\*/g, "[^/]+")}$`;
    // "*" matches one path segment, e.g. "/device/*/details" matches "/device/abc123/details"
    cy.location("pathname").should("match", new RegExp(pattern));
    return;
  }

  cy.location("pathname").should("eq", expectedFullPath);
});
