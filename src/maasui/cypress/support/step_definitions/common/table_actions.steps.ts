import { Then, When } from "@badeball/cypress-cucumber-preprocessor";
import { LONG_TIMEOUT } from "../../../constants";

export function findRow(identifier: string, timeout?: number) {
  const hasSelectors = identifier
    .split(/\s+/)
    .map((part) => `:has(:contains("${part}"))`)
    .join("");
  return cy.get(`tr${hasSelectors}`, timeout ? { timeout } : undefined);
}

Then("the user selects all rows", () => {
  cy.findByRole("checkbox", { name: "select all" }).click({ force: true });
});

Then(
  "a row matching {string} should be visible in the table",
  (rowIdentifier: string) => {
    findRow(rowIdentifier, LONG_TIMEOUT).should("exist");
  }
);

Then(
  "a row matching {string} should not be visible in the table",
  (rowIdentifier: string) => {
    findRow(rowIdentifier, LONG_TIMEOUT).should("not.exist");
  }
);

Then(
  "the {string} row action for the {string} row should be enabled",
  (action: string, rowIdentifier: string) => {
    findRow(rowIdentifier)
      .findByRole("button", { name: action, timeout: LONG_TIMEOUT })
      .should("not.have.attr", "aria-disabled", "true");
  }
);

When(
  "the user clicks the {string} row action for the {string} row",
  (action: string, rowIdentifier: string) => {
    findRow(rowIdentifier).findByRole("button", { name: action }).click();
  }
);
