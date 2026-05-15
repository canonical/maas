import { Then, When } from "@badeball/cypress-cucumber-preprocessor";

Then("the {string} button should be enabled", (button: string) => {
  cy.findByRole("button", {
    name: button,
  }).should("not.have.attr", "aria-disabled", "true");
});

When("the user clicks the {string} button", (button: string) => {
  cy.findByRole("button", { name: button }).click();
});

When("the user clicks the button matching {string}", (button: string) => {
  cy.findByRole("button", { name: new RegExp(button, "i") }).click();
});

When("the user submits the form", () => {
  cy.get("button[type='submit']").click();
});

When("the user clicks the {string} link", (link: string) => {
  cy.findByRole("link", { name: link }).click();
});

When(
  "the user clicks the {string} link in the main navigation",
  (linkName: string) => {
    cy.getMainNavigation()
      .should("be.visible")
      .within(() =>
        cy.findByRole("link", { name: new RegExp(linkName, "i") }).click()
      );
  }
);

When("the user refreshes the page", () => {
  cy.reload(true);
});

When("the user expands the {string} accordion section", (title: string) => {
  cy.findByRole("heading", { name: title }).click();
});

When("the user opens the dropdown for {string}", (release: string) => {
  const hasSelectors = release
    .split(/\s+/)
    .map((part) => `:has(:contains("${part}"))`)
    .join("");
  cy.get(`tr${hasSelectors}`).findByRole("combobox").click();
});

When("the user selects the first available option", () => {
  cy.get(".multi-select__dropdown").find(".p-checkbox__label").first().click();
});

When("the user selects {string}", (option: string) => {
  cy.get(".multi-select__dropdown")
    .contains(".p-checkbox__label", option)
    .click();
});

When("the user presses the {string} key", (key: string) => {
  cy.get("body").type(`{${key}}`);
});
