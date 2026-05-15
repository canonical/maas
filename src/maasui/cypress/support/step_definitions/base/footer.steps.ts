import { Then, When } from "@badeball/cypress-cucumber-preprocessor";

When("the user looks for the {string} link", (linkName: string) => {
  cy.findByRole("link", { name: new RegExp(linkName, "i") }).as("element");
});

Then("the link should include {string}", (expectedHref) => {
  cy.get("@element").should("have.attr", "href").and("include", expectedHref);
});
