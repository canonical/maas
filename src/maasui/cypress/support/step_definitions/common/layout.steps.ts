import { Then } from "@badeball/cypress-cucumber-preprocessor";

Then("the main toolbar heading should be {string}", (expectedHeading) => {
  cy.get("[data-testid='main-toolbar-heading']").should(
    "contain",
    expectedHeading
  );
});

Then("the side navigation title should be {string}", (expectedHeading) => {
  cy.get(".p-side-navigation__title").should("contain", expectedHeading);
});

Then("the heading should be {string}", (expectedHeading: string) => {
  cy.findByRole("heading", { level: 1 }).contains(expectedHeading);
});

Then("the heading matching {string} text should exist", (heading: string) => {
  cy.findByRole("heading", { name: new RegExp(heading, "i") }).should("exist");
});

Then("the {string} header should not exist", (headerName: string) => {
  cy.findByRole("header", { name: headerName }).should("not.exist");
});

Then("the text matching {string} should exist", (text: string) => {
  cy.findByText(new RegExp(text, "i")).should("exist");
});

Then("the side panel should not be visible", () => {
  cy.get("#aside-panel").should("not.be.visible");
});
