import { Given } from "@badeball/cypress-cucumber-preprocessor";

Given("the viewport is {string}", (viewport: Cypress.ViewportPreset) => {
  cy.viewport(viewport);
});

Given("the page is loaded", () => {
  cy.waitForPageToLoad();
});

Given("the {string} table has loaded", (name: string) => {
  cy.waitForTableToLoad({ name: name });
});
