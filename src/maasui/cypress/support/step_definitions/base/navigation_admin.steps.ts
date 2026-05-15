import { Then, When } from "@badeball/cypress-cucumber-preprocessor";

When(
  'the user clicks the "{string}" link in the main navigation',
  (linkName: string) => {
    cy.getMainNavigation().within(() =>
      cy.findByRole("link", { name: linkName }).click()
    );
  }
);

When("the user clicks the username link in the main navigation", () => {
  const username = Cypress.env("username");
  cy.getMainNavigation().within(() =>
    cy.findByRole("link", { name: username }).should("be.visible").click()
  );
});

Then("the username navigation item should be selected", () => {
  const username = Cypress.env("username");
  cy.get(".p-side-navigation__item.is-selected a").should("contain", username);
});

Then("the username link should have current page state", () => {
  const username = Cypress.env("username");
  cy.findAllByRole("link", { current: "page", name: username }).should("exist");
});

Then(
  /^the\s+"([^"]+)"\s+link should have current page state\s*$/,
  (linkName: string) => {
    cy.findAllByRole("link", { current: "page", name: linkName }).should(
      "exist"
    );
  }
);
