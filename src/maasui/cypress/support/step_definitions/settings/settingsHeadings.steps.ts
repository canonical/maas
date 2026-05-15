import { Then } from "@badeball/cypress-cucumber-preprocessor";

Then("the {string} heading should exist", (heading: string) => {
  cy.findByRole("heading", { name: heading }).should("exist");
});
