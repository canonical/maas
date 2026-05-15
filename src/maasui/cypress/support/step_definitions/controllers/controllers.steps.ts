import { Given, Then, When } from "@badeball/cypress-cucumber-preprocessor";
import { generateId } from "../../../e2e/utils";

Given("the user navigates to details page of the first controller", () => {
  cy.findByRole("grid", { name: /controllers list/i }).within(() =>
    cy.findAllByRole("link").first().click()
  );
  cy.waitForPageToLoad();
});

When("the user adds a tag to the controller", () => {
  const tagName = `tag-${generateId()}`;
  cy.wrap(tagName).as("createdTag");

  // can add a tag to the controller
  cy.findByRole("link", {
    name: /Configuration/,
  }).click();
  cy.findAllByRole("button", {
    name: /Edit/,
  })
    .first()
    .click();

  cy.findByRole("form", { name: /Controller configuration/ }).should("exist");
  cy.get("input[placeholder='Create or remove tags']").type(
    `${tagName}{enter}`
  );
  cy.findByRole("button", { name: /Create and add to tag changes/ }).click();
  cy.findByRole("button", { name: /Save changes/ }).click();

  cy.findByRole("link", { name: /Summary/ }).click();
  cy.findByTestId("machine-tags").contains(tagName);
});

When("the user clicks the created tag", () => {
  cy.findByRole("link", {
    name: /Configuration/,
  }).click();
  cy.get<string>("@createdTag").then((tagName) => {
    cy.findByRole("link", { name: tagName }).click();
  });
});

When("the user clicks name of the first script", () => {
  cy.findByRole("grid").within(() => {
    cy.get("tbody tr")
      .first()
      .within(() => {
        cy.findByTestId("details-link").click();
      });
  });
});

Then("the correct tag is displayed in the searchbox", () => {
  cy.get("@createdTag").then((tagName) => {
    cy.findByRole("searchbox", { name: /Search/ }).should(
      "have.value",
      `tags:(=${tagName})`
    );
  });
});

Then("the correct number of controllers is displayed", () => {
  cy.findByRole("grid", { name: "controllers list" }).within(() => {
    cy.get("tbody tr").should("have.length", 1);
  });
});
Then("the {string} action should exist", (action: string) => {
  cy.findByRole("button", {
    name: new RegExp(action, "i"),
  }).should("exist");
});
Then("the {string} action should not exist", (action: string) => {
  cy.findByRole("button", {
    name: new RegExp(action, "i"),
  }).should("not.exist");
});
