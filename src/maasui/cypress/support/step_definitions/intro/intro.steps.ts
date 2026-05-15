import { Given, Then, When } from "@badeball/cypress-cucumber-preprocessor";
import { generateMAASURL } from "../../../e2e/utils";

Given("the user is logged in before the intro is completed", () => {
  cy.login({
    shouldSkipIntro: false,
    shouldSkipSetupIntro: false,
  });
});

When("the user saves the MAAS setup", () => {
  cy.findByRole("heading", { name: /Welcome to MAAS/i, level: 1 }).should(
    "exist"
  );
  cy.waitForPageToLoad();
  cy.findByRole("button", { name: /Save/i }).click();
});

When("the user skips the initial setup", () => {
  cy.findByRole("heading", { name: /Welcome to MAAS/i, level: 1 }).should(
    "exist"
  );
  cy.findByRole("button", { name: /Skip/i }).click();
  cy.findByText(
    /Are you sure you want to skip the initial MAAS setup?/i
  ).should("exist");
  cy.findByRole("button", { name: /Skip/i }).click();
});

Then("the intro page should be displayed", () => {
  cy.findByRole("heading", { name: /Welcome to MAAS/i, level: 1 }).should(
    "exist"
  );
  cy.location("pathname").should("eq", generateMAASURL("/intro"));
});

Then("the user should be redirected to the images setup page", () => {
  cy.findByRole("heading", { name: /Images synced from/i, level: 1 }).should(
    "exist"
  );
  cy.location("pathname").should("eq", generateMAASURL("/intro/images"));
});

Then("the user should be redirected to the user setup page", () => {
  cy.findByRole("heading", { name: /SSH keys/i, level: 1 }).should("exist");
  cy.location("pathname").should("eq", generateMAASURL("/intro/user"));
});
