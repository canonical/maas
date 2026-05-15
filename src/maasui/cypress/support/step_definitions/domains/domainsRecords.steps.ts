import { Then, When } from "@badeball/cypress-cucumber-preprocessor";
import { generateName } from "../../../e2e/utils";

const escapeRegExp = (value: string) =>
  value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

When("the user enters a record name", () => {
  const recordName = generateName("dns-record");

  Cypress.env("dnsRecordName", recordName);
  cy.get("#aside-panel").within(() => {
    cy.get("input[name='name']").type(recordName);
  });
});

When("the DNS default domain row is opened", () => {
  cy.findByRole("grid", { name: "Domains table" }).within(() => {
    cy.get("[data-testid='domain-name']").first().click();
  });
});

When('the user enters the same IP address in the "data" field', () => {
  const knownDeviceIp = String(Cypress.env("knownDeviceIp") || "");

  expect(knownDeviceIp, "known device IP").to.not.equal("");
  cy.get("#aside-panel").within(() => {
    cy.get("input[name='rrdata']").type(knownDeviceIp);
  });
});

Then("the record name should appear as a link in the DNS record list", () => {
  const recordName = String(Cypress.env("dnsRecordName") || "");

  expect(recordName, "DNS record name").to.not.equal("");
  cy.findByRole("link", {
    name: new RegExp(`^${escapeRegExp(recordName)}$`),
  }).should("exist");
});

When("the created DNS record link is opened", () => {
  const recordName = String(Cypress.env("dnsRecordName") || "");

  expect(recordName, "DNS record name").to.not.equal("");
  cy.findByRole("link", {
    name: new RegExp(`^${escapeRegExp(recordName)}$`),
  }).click();
});
