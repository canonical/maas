import { Then } from "@badeball/cypress-cucumber-preprocessor";

Then("the groups list has an {string} button", (button: string) => {
  cy.findByRole("button", { name: button }).should("exist");
});
