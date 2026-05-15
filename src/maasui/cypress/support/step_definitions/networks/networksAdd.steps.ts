import { Then, When } from "@badeball/cypress-cucumber-preprocessor";
import {
  generateCidr,
  generateId,
  generateMAASURL,
  generateVid,
} from "../../../e2e/utils";
import { completeAddVlanForm, completeForm } from "./add.helpers";

When("the user creates a new fabric", function () {
  this.fabric = `cy-fabric-${generateId()}`;

  completeForm("Fabric", this.fabric);
});

When("the user creates a new space", function () {
  this.spaceName = `cy-space-${generateId()}`;

  completeForm("Space", this.spaceName);
});

When("the user creates a new VLAN", function () {
  this.vid = generateVid();
  this.vlan = `cy-vlan-${this.vid}`;

  completeAddVlanForm(this.vid, this.vlan, this.fabric!, this.spaceName!);
});

When("the user creates a new subnet", function () {
  this.cidr = generateCidr();
  this.subnetName = `cy-subnet-${generateId()}`;

  cy.addSubnet({
    subnetName: this.subnetName,
    cidr: this.cidr,
    fabric: this.fabric!,
    vid: this.vid!,
    vlan: this.vlan!,
  });
});

When("the user deletes the created subnet", function () {
  cy.findByRole("link", { name: new RegExp(this.subnetName) }).click({
    force: true,
  });
  cy.findByRole("heading", { name: "Subnet summary" }).should("exist");

  cy.findByRole("button", { name: "Take action" }).click();
  cy.findByRole("button", { name: "Delete subnet" }).click();
  cy.findByText(/Are you sure you want to delete this subnet?/).should(
    "be.visible"
  );
  cy.findByRole("button", { name: "Delete" }).click();

  cy.url().should("include", generateMAASURL("/networks/subnets?by=fabric"));
});

When("the user tries to add a VLAN with a VID that already exists", () => {
  const vid = generateVid();
  const name = `cypress-${vid}`;
  completeAddVlanForm(vid, name);
  completeAddVlanForm(vid, name);
});

When("the user tries to add a Fabric with a name that already exists", () => {
  const name = `cypress-${generateId()}`;
  completeForm("Fabric", name);
  completeForm("Fabric", name);
});

When("the user tries to add a Space with a name that already exists", () => {
  const name = `cypress-${generateId()}`;
  completeForm("Space", name);
  completeForm("Space", name);
});

Then("the subnet appears under the correct fabric", function () {
  cy.findByRole("button", { name: "Save VLAN" }).should("not.exist");
  cy.findByRole("searchbox", { name: "Search" }).type(this.fabric!);

  cy.findAllByRole("link", { name: this.fabric }).should("have.length", 1);

  cy.findAllByRole("row", { name: new RegExp(this.fabric) })
    .next("tr")
    .within(() => {
      cy.findAllByRole("cell").eq(1).should("contain.text", this.subnetName);
      cy.findAllByRole("cell")
        .eq(2)
        .should("have.text", `${this.vid} (${this.vlan})`);
      cy.findAllByRole("cell").eq(5).should("have.text", this.spaceName);
    });
});

Then("fabric list should not include deleted subnet", function () {
  cy.findByRole("link", { name: new RegExp(this.subnetName) }).should(
    "not.exist"
  );
});

Then("text {string} should be visible", (text: string) => {
  cy.findByText(new RegExp(text, "i")).should("be.visible");
});

When("the user creates a subnet with a known CIDR", () => {
  const subnetName = `cy-known-subnet-${generateId()}`;
  const cidr = `192.168.${Math.floor(Math.random() * 100) + 100}.0/24`;
  const knownIp = cidr.replace(".0/24", ".25");

  Cypress.env("knownSubnetName", subnetName);
  Cypress.env("knownSubnetCidr", cidr);
  Cypress.env("knownDeviceIp", knownIp);
  Cypress.env("useKnownDeviceIpForDnsRecordTest", true);

  cy.findByRole("button", { name: "Add" }).click();
  cy.findByRole("button", { name: "Subnet" }).click();
  cy.findByRole("textbox", { name: "CIDR" }).type(cidr);
  cy.findByRole("textbox", { name: "Name" }).type(subnetName);

  cy.findByRole("combobox", { name: "Fabric" })
    .find("option")
    .then(($options) => {
      const values = [...$options]
        .map((option) => option.getAttribute("value"))
        .filter((value): value is string => !!value);

      expect(values.length, "available fabric options").to.be.greaterThan(0);
      cy.findByRole("combobox", { name: "Fabric" }).select(values[0]);
    });

  cy.findByRole("combobox", { name: "VLAN" })
    .find("option")
    .then(($options) => {
      const values = [...$options]
        .map((option) => option.getAttribute("value"))
        .filter((value): value is string => !!value);

      expect(values.length, "available VLAN options").to.be.greaterThan(0);
      cy.findByRole("combobox", { name: "VLAN" }).select(values[0]);
    });

  cy.findByRole("button", { name: "Save subnet" }).click();
  cy.findByRole("link", { name: new RegExp(subnetName) }).should("exist");
});
