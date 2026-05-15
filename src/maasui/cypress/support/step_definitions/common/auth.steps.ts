import { Given } from "@badeball/cypress-cucumber-preprocessor";

Given("the user is logged in", () => {
  cy.login();
});
