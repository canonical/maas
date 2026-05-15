import { Given, Then, When } from "@badeball/cypress-cucumber-preprocessor";
import { generateMAASURL } from "../../../e2e/utils";

Given("no group parameter has been set", () => {
  cy.findByRole("combobox", { name: /group by/i }).should(
    "have.value",
    "fabric"
  );
});

When("the user selects grouping by space", () => {
  cy.findByRole("combobox", { name: /group by/i }).select("space");

  cy.waitForPageToLoad();
});

Then("correct headers exist", () => {
  const expectedHeaders = ["VLAN", "DHCP", "Subnet", "Available IPs", "Space"];

  cy.findByRole("grid", { name: "Subnets by fabric" }).within(() => {
    expectedHeaders.forEach((name) => {
      cy.findByRole("columnheader", { name }).should("exist");
    });
  });
});

Then("the URL gets updated to default grouping", () => {
  cy.findByRole("combobox", { name: /group by/i }).should(
    "have.value",
    "fabric"
  );

  cy.url().should("include", generateMAASURL("/networks/subnets?by=fabric"));
});

Then("subnets are by default grouped by fabric", () => {
  cy.findByRole("grid", { name: "Subnets by fabric" }).within(() => {
    cy.get("tbody tr").first().should("include.text", "fabric");
  });

  cy.findByRole("combobox", { name: /group by/i }).should(
    "have.value",
    "fabric"
  );

  cy.findByRole("combobox", { name: /group by/i }).should(
    "not.have.value",
    "space"
  );
});

Then("subnets are grouped by space", () => {
  cy.findByRole("grid", { name: "Subnets by space" }).within(() => {
    cy.get("tbody tr").first().should("include.text", "space");
  });

  cy.url().should("include", generateMAASURL("/networks/subnets?by=space"));
});
