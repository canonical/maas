import { Given, Then, When } from "@badeball/cypress-cucumber-preprocessor";
import { generateMac, generateTag } from "../../../e2e/utils";

let tag = "";

Given("the user adds a new device", () => {
  cy.findByRole("button", { name: /Add device/ }).click();
  const mac = generateMac();
  cy.findByLabelText(/Device name/).type("cypress-device");
  cy.get("input[placeholder='00:00:00:00:00:00']").type(mac);
  cy.findByRole("button", { name: /Save device/ }).click();
});

When("the user opens the device configuration", () => {
  cy.findByRole("link", { name: /cypress-device/ }).click();

  cy.findByRole("link", {
    name: /Configuration/,
  }).click();
});

When("the user adds a tag to the device", () => {
  tag = generateTag();
  cy.findByRole("button", {
    name: /Edit/,
  }).click();
  cy.get("input[placeholder='Create or remove tags']").clear();
  cy.get("input[placeholder='Create or remove tags']").type(tag);

  cy.findByRole("button", {
    name: new RegExp(`Create tag "${tag}"`),
  }).click();

  cy.findByRole("button", {
    name: /Create and add to tag changes/,
  }).click();

  cy.findByRole("button", { name: /Save changes/ }).click();
});

Then("the section header title should be {string}", (expectedTitle: string) => {
  cy.get("[data-testid='section-header-title']").should(
    "contain",
    expectedTitle
  );
});

Then("the tag should be visible in the device summary", () => {
  cy.findByRole("link", { name: /Summary/ }).click();
  cy.findByText(new RegExp(tag, "i")).should("exist");
});
