import { Then, When } from "@badeball/cypress-cucumber-preprocessor";
import { customAlphabet } from "nanoid";
import { generateEmail } from "../../../../e2e/utils";

const nanoid = customAlphabet("1234567890abcdefghi", 10);
let username = "";

When("the user fills in valid user details", () => {
  username = nanoid();
  const password = nanoid();
  cy.get("input[name='username']").type(username);
  cy.get("input[name='email']").type(generateEmail());
  cy.get("input[name='password']").type(password);
  cy.get("input[name='passwordConfirm']").type(password);
});

Then("the user creation request should succeed", () => {
  cy.findByText("Add user").should("not.exist");
  cy.findByText(username).should("exist");
});
