import { Given, Then, When } from "@badeball/cypress-cucumber-preprocessor";
import {
  expectCollapsedNavigation,
  expectExpandedNavigation,
} from "./navigation.helpers";

Given("the navigation is collapsed", () => {
  expectCollapsedNavigation();
});

Given("the main navigation should not be visible", () => {
  cy.getMainNavigation().should("not.be.visible");
});

When("the user presses {string} key", (key: string) => {
  cy.get("body").type(key);
});

When(
  "the user clicks the {string} button in the navigation banner",
  (buttonName: string) => {
    cy.findByRole("banner", { name: "navigation" }).within(() =>
      cy.findByRole("button", { name: buttonName }).click()
    );
  }
);

When(
  "the user clicks the {string} button in the main navigation",
  (buttonName: string) => {
    cy.getMainNavigation()
      .should("be.visible")
      .within(() =>
        cy.findByRole("button", { name: new RegExp(buttonName, "i") }).click()
      );
  }
);

Then("the navigation is expanded", () => {
  expectExpandedNavigation();
});

Then("the main navigation should be visible", () => {
  cy.getMainNavigation().should("be.visible");
});
