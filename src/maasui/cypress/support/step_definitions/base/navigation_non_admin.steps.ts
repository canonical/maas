import { Given, Then } from "@badeball/cypress-cucumber-preprocessor";

Given("the user is logged in as a non-admin", () => {
  cy.loginNonAdmin();
});

Then("the {string} navigation item should be selected", (itemName: string) => {
  cy.get(".p-side-navigation__item.is-selected a").contains(itemName);
});
