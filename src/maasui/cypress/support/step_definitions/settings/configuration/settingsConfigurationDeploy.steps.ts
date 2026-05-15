import { Then } from "@badeball/cypress-cucumber-preprocessor";

Then("the deploy configuration form should be displayed", () => {
  cy.findByRole("form", { name: /deploy configuration/i }).should("exist");
});

Then(
  "the {string} field should have the value {string}",
  (fieldName: string, value: string) => {
    cy.findByRole("textbox", { name: new RegExp(fieldName, "i") }).should(
      "have.value",
      value
    );
  }
);
