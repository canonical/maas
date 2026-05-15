import { Given, Then, When } from "@badeball/cypress-cucumber-preprocessor";
import { LONG_TIMEOUT } from "../../../constants";
import { generateMAASURL } from "../../../e2e/utils";
import { completeAddMachineForm } from "./machines.helpers";

let machineName: string;

Given("the user creates a machine through the add machine flow", () => {
  ({ name: machineName } = completeAddMachineForm());
  cy.findByRole("heading", { name: /Add machine/i }).should("not.exist");
});

Given("the user searches for the created machine", () => {
  cy.findByRole("searchbox").type(machineName);
  cy.findByRole("grid", { name: /Loading/i }).should("not.exist");
});

When("the user opens the created machine details", () => {
  cy.findByRole("link", {
    name: new RegExp(machineName, "i"),
    timeout: LONG_TIMEOUT,
  }).click();
});

When("the user opens the {string} tab", (tab: string) => {
  cy.findByRole("link", { name: new RegExp(tab, "i") }).click();
});

When("the user switches to an ipad mini landscape viewport", () => {
  cy.viewport("ipad-mini", "landscape");
});

When("the user deletes the current machine", () => {
  cy.findByRole("button", { name: /Menu/i }).click();
  cy.findByRole("button", { name: /Delete/i }).click();
  cy.findByRole("button", { name: /Delete machine/i }).click();
  cy.waitForPageToLoad();
});

When("the user opens the machine actions menu", () => {
  cy.waitForPageToLoad();
  cy.findByRole("button", {
    name: /Actions/i,
  }).click();
});

When("the user aborts commissioning", () => {
  cy.findByLabelText("Actions submenu").within(() => {
    cy.findByRole("button", { name: /Abort/i }).should("be.visible");

    cy.findByRole("button", { name: /Abort/i }).click({ force: true });
  });

  cy.findByRole("button", { name: /Abort actions/i })
    .should("be.visible")
    .and("not.be.disabled");
  cy.findByRole("button", { name: /Abort actions/i }).click();
});

When("the user deletes the machine", () => {
  cy.findByRole("button", { name: /Delete/i }).click();
  cy.findByRole("button", { name: /Delete machine/i }).click();
  cy.waitForPageToLoad();
});

When("the user opens the first commissioning details row", () => {
  cy.findByRole("grid").within(() => {
    cy.get("tbody tr")
      .first()
      .within(() => {
        cy.findByTestId("details-link", { timeout: LONG_TIMEOUT }).click();
      });
  });
  cy.waitForPageToLoad();
});

Then("the ip column header should exist", () => {
  cy.findAllByRole("columnheader", { name: /IP/i }).first().should("exist");
});

Then("the subnet column header should exist", () => {
  cy.findByRole("columnheader", { name: /subnet/i })
    .first()
    .should("exist");
});

Then("the {string} column header should not exist", (column: string) => {
  cy.findByRole("columnheader", { name: new RegExp(column, "i") }).should(
    "not.exist"
  );
});

Then("the user should be redirected to the machines page", () => {
  cy.url().should("include", generateMAASURL("/machines"));
});

Then(
  "the sub-heading matching {string} text should exist",
  (heading: string) => {
    cy.findByRole("heading", {
      level: 2,
      name: new RegExp(heading, "i"),
    }).should("exist");
  }
);
