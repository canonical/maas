import { Then, When } from "@badeball/cypress-cucumber-preprocessor";
import { generateRefreshTokenLifetime } from "../../../../e2e/utils";

When("the user clears the {string} field", (fieldName: string) => {
  cy.findByRole("textbox", { name: fieldName }).clear();
});

When(
  "the user enters new value into the refresh token expiration field",
  () => {
    const value = generateRefreshTokenLifetime();
    cy.findByRole("textbox", { name: "Refresh token expiration" }).type(value);
  }
);

When("the user saves the token expiration settings if possible", () => {
  cy.findByRole("button", { name: "Save" }).then(($button) => {
    if ($button.is(":disabled")) {
      return;
    } else {
      cy.wrap($button).click();
    }
  });
});

Then("the login form should be displayed", () => {
  cy.waitForPageToLoad();
  cy.findByRole("form", { name: "Login" }).should("exist");
});
