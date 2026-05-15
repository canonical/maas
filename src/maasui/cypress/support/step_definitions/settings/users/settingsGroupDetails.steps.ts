import { Then, When } from "@badeball/cypress-cucumber-preprocessor";
import { customAlphabet } from "nanoid";

const nanoid = customAlphabet("1234567890abcdefghi", 10);
let groupName = "";

When("the user fills in valid group details", () => {
  groupName = `cy-group-${nanoid()}`;
  cy.get("input[name='name']").type(groupName);
});

Then("the group creation should succeed", () => {
  cy.findByText("Save group").should("not.exist");
  cy.findByText(groupName).should("exist");
});

When("the user clicks the created group", () => {
  cy.findByRole("link", { name: groupName }).click();
});

Then("the group details page should display the group name", () => {
  cy.contains(groupName).should("exist");
});
