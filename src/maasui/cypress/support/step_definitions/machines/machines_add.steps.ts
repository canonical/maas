import { Given, When } from "@badeball/cypress-cucumber-preprocessor";
import { customAlphabet } from "nanoid";
import { generateMac } from "../../../e2e/utils";

const nanoid = customAlphabet("1234567890abcdefghi", 10);

Given("the user opens the add machine form", () => {
  cy.findByRole("button", { name: "Add hardware" }).click();
  cy.get(".p-contextual-menu__link").contains("Machine").click();
});

Given("the {string} heading is visible", (heading: string) => {
  cy.findByRole("heading", { name: heading }).should("be.visible");
});

When("the user fills in valid machine details", () => {
  const hostname = `cypress-${nanoid()}`;
  cy.get("input[name='hostname']").type(hostname);
  cy.get("input[name='pxe_mac']").type(generateMac());
  cy.get("select[name='power_type']").select("manual");
  cy.get("select[name='power_type']").blur();
});
