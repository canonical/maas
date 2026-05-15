import { Given, Then } from "@badeball/cypress-cucumber-preprocessor";

Given("the user expands the main navigation", () => {
  cy.expandMainNavigation();
});

Given("the side panel is visible", () => {
  cy.get("#aside-panel").should("be.visible");
});

Given("the {string} panel is visible", (panelName: string) => {
  cy.findByRole("complementary", { name: panelName }).should("be.visible");
});

Then("the {string} panel should not exist", (panelName: string) => {
  cy.findByRole("complementary", { name: panelName }).should("not.exist");
});
