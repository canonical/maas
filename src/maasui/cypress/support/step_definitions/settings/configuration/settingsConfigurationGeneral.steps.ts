import { Given, Then, When } from "@badeball/cypress-cucumber-preprocessor";

Given("the default theme is applied", () => {
  cy.findByRole("radio", { name: "Default" }).click();

  cy.findByRole("button", { name: "Save" }).then(($button) => {
    if ($button.is(":disabled")) {
      return;
    }

    cy.wrap($button).click();
  });
});

When("the user selects the {string} theme", (themeName: string) => {
  cy.findByRole("radio", { name: themeName }).click();
});

When("the user toggles the {string} checkbox", (label: string) => {
  cy.findByLabelText(new RegExp(label, "i")).click({ force: true });
});

Then(
  "the main navigation should use the {string} theme class",
  (className: string) => {
    cy.getMainNavigation().should("have.class", className);
  }
);

Then("the {string} button should be disabled", (buttonName: string) => {
  cy.findByRole("button", { name: buttonName }).should("be.disabled");
});

Then("the {string} checkbox should be checked", (label: string) => {
  cy.findByLabelText(new RegExp(label, "i")).should("be.checked");
});

Then("the {string} checkbox should not be checked", (label: string) => {
  cy.findByLabelText(new RegExp(label, "i")).should("not.be.checked");
});
