import { Given, Then, When } from "@badeball/cypress-cucumber-preprocessor";

Given(
  "the skipsetupintro cookie is set to {string}",
  (value: "true" | "false") => {
    cy.setCookie("skipsetupintro", value);
  }
);

Given("the skipintro cookie is set to {string}", (value: "true" | "false") => {
  cy.setCookie("skipintro", value);
});

When("the user enters invalid username and password", () => {
  cy.findByRole("textbox", { name: /Username/ }).type("user");
  cy.findByRole("button", { name: /Next/ }).click();
  cy.findByLabelText(/Password/).type("invalid-password");
  cy.findByRole("button", { name: /Login/ }).click();
});

When("the user provides correct username and password", () => {
  cy.get("input[name='username']").type(Cypress.env("username"));
  cy.findByRole("button", { name: /Next/ }).click();
  cy.get("input[name='password']").type(Cypress.env("password"));
  cy.get("button[type='submit']").click();
});

When("the user clicks on the {string} button", (buttonText: string) => {
  cy.get("input[name='username']").type("johndoe");
  cy.findByRole("button", { name: /Next/ }).click();
  cy.findByRole("button", { name: new RegExp(buttonText, "i") }).click();

  // Log in at keycloak
  cy.origin(
    `${Cypress.env("KEYCLOAK_URL")}:${Cypress.env("KEYCLOAK_PORT")}`,
    () => {
      cy.get("input[name='username']").type("johndoe");
      cy.get("input[name='password']").type("abc123");
      cy.get("button[type='submit']").click();
    }
  );
});

Then("the alert {string} should be visible", (text: string) => {
  cy.findByRole("alert").should("be.visible").should("include.text", text);
});
