import { Then, When } from "@badeball/cypress-cucumber-preprocessor";
import { customAlphabet } from "nanoid";
import { generateMAASURL } from "../../../e2e/utils";

const nanoid = customAlphabet("1234567890abcdefghi", 10);
let newUsername = "";
let newPassword = "";

When("the admin creates a new user account", () => {
  newUsername = `cy-user-${nanoid()}`;
  newPassword = `Pass${nanoid()}!`;

  cy.visit(generateMAASURL("/settings/user-management/users"));
  cy.waitForPageToLoad();
  cy.findByRole("button", { name: /Add user/i }).click();
  cy.get("input[name='username']").type(newUsername);
  cy.get("input[name='email']").type(`${newUsername}@example.com`);
  cy.get("input[name='password']").type(newPassword);
  cy.get("input[name='passwordConfirm']").type(newPassword);
  cy.get("button[type='submit']").click();
  cy.findByText(newUsername).should("exist");
});

When("the admin logs out", () => {
  cy.clearCookies();
});

When("the new user logs in with their credentials", () => {
  cy.login({
    username: newUsername,
    password: newPassword,
    shouldSkipIntro: false,
    shouldSkipSetupIntro: true,
  });
  cy.visit(generateMAASURL("/"));
  cy.waitForPageToLoad();
});

Then("the SSH keys import prompt should be visible", () => {
  cy.findByTestId("section-header-title")
    .contains(/SSH keys/i)
    .should("exist");
});
