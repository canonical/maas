import { Given, Then, When } from "@badeball/cypress-cucumber-preprocessor";
import { LONG_TIMEOUT } from "../../../constants";
import {
  generateCidr,
  generateId,
  generateMAASURL,
  generateMac,
  generateVid,
} from "../../../e2e/utils";
import { completeAddVlanForm, completeForm } from "./add.helpers";

Given("the user has created a dedicated subnet with a mask of 24", function () {
  this.subnetFabric = `cy-fabric-${generateId()}`;
  const vid = generateVid();
  this.subnetVlan = `cy-vlan-${vid}`;
  this.subnetCidr = generateCidr(); // always produces 192.168.x.0/24
  this.subnetName = `cy-subnet-${generateId()}`;

  completeForm("Fabric", this.subnetFabric);
  completeAddVlanForm(vid, this.subnetVlan, this.subnetFabric);
  cy.addSubnet({
    subnetName: this.subnetName,
    cidr: this.subnetCidr,
    fabric: this.subnetFabric,
    vid,
    vlan: this.subnetVlan,
  });
});

When(
  "the user navigates to the address reservation page of the dedicated subnet",
  function () {
    cy.findByRole("link", { name: new RegExp(this.subnetName) }).click({
      force: true,
    });
    cy.findByRole("heading", { name: "Subnet summary" }).should("exist");
    cy.findByRole("link", { name: /address reservation/i }).click();
    cy.waitForPageToLoad();
  }
);

When("the user navigates to the address reservation tab", () => {
  cy.findByRole("link", { name: /address reservation/i }).click();
  cy.waitForPageToLoad();
});

When("the user reserves a static DHCP lease", function () {
  this.reservedIpSuffix = "200";
  this.reservedMac = generateMac();
  this.reservedComment = `cy-comment-${generateId()}`;

  cy.findByRole("button", { name: /reserve static dhcp lease/i }).click();

  cy.findByRole("complementary", { name: /reserve dhcp lease/i }).within(() => {
    cy.findByRole("textbox", { name: /ip address/i }).type(
      this.reservedIpSuffix
    );
    cy.findByRole("textbox", { name: /mac address/i }).type(this.reservedMac);
    cy.findByRole("textbox", { name: /comment/i }).type(this.reservedComment);
  });

  cy.findByRole("complementary", { name: /reserve dhcp lease/i }).within(() =>
    cy
      .findByRole("button", { name: /reserve static dhcp lease/i })
      .last()
      .click()
  );

  cy.findByRole("complementary", { name: /reserve dhcp lease/i }).should(
    "not.exist",
    { timeout: LONG_TIMEOUT }
  );
});

Then("the new static DHCP lease appears in the table", function () {
  cy.findByRole("table", { name: /static dhcp leases/i }).within(() => {
    cy.findByText(new RegExp(this.reservedMac, "i")).should("exist");
  });
});

When("the user edits the static DHCP lease comment", function () {
  this.updatedComment = `cy-updated-${generateId()}`;

  cy.findByRole("table", { name: /static dhcp leases/i }).within(() => {
    cy.findByText(new RegExp(this.reservedMac, "i"))
      .closest("tr")
      .findByRole("button", { name: /edit/i })
      .click();
  });

  cy.findByRole("complementary", {
    name: /edit dhcp lease/i,
  }).within(() => {
    cy.findByRole("textbox", { name: /comment/i })
      .clear()
      .type(this.updatedComment);
    cy.findByRole("button", { name: /update static dhcp lease/i }).click();
  });

  cy.findByRole("complementary", {
    name: /edit static dhcp lease/i,
  }).should("not.exist", { timeout: LONG_TIMEOUT });
});

Then(
  "the updated comment is visible in the static DHCP leases table",
  function () {
    cy.findByRole("table", { name: /static dhcp leases/i }).within(() => {
      cy.findByText(this.updatedComment).should("exist");
    });
  }
);

When("the user deletes the static DHCP lease", function () {
  cy.findByRole("table", { name: /static dhcp leases/i }).within(() => {
    cy.findByText(new RegExp(this.reservedMac, "i"))
      .closest("tr")
      .findByRole("button", { name: /delete/i })
      .click();
  });

  cy.findByRole("complementary", { name: /delete/i }).within(() => {
    cy.findByRole("button", { name: /delete/i }).click();
  });

  cy.findByRole("complementary", { name: /delete/i }).should("not.exist", {
    timeout: LONG_TIMEOUT,
  });
});

Then("the static DHCP lease should not exist", function () {
  cy.findByRole("table", { name: /static dhcp leases/i }).within(() => {
    cy.findByText(new RegExp(this.reservedMac, "i")).should("not.exist");
  });
});

Given("the user has created a machine with a known MAC address", function () {
  this.machineMac = generateMac();
  this.machineName = `cy-machine-${generateId()}`;

  cy.visit(generateMAASURL("/machines"));
  cy.waitForPageToLoad();

  cy.findByRole("button", { name: "Add hardware" }).click();
  cy.get(".p-contextual-menu__link")
    .contains("Machine", { timeout: LONG_TIMEOUT })
    .click();
  cy.findByLabelText("Machine name").type(this.machineName);
  cy.findByLabelText("MAC address").type(this.machineMac);
  cy.findByLabelText("Power type").select("Manual");
  cy.findByLabelText("Power type").blur();
  cy.get("button[type='submit']").click();

  cy.findByRole("heading", { name: /Add machine/i }).should("not.exist");
});

When("the user reserves a static DHCP lease for the machine", function () {
  this.reservedMac = this.machineMac;
  this.reservedComment = `cy-machine-comment-${generateId()}`;

  cy.findByRole("button", { name: /reserve static dhcp lease/i }).click();

  cy.findByRole("complementary", { name: /reserve dhcp lease/i }).within(() => {
    cy.findByRole("textbox", { name: /ip address/i }).type("2");
    cy.findByRole("textbox", { name: /mac address/i }).type(this.reservedMac);
    cy.findByRole("textbox", { name: /comment/i }).type(this.reservedComment);
  });

  cy.findByRole("complementary", { name: /reserve dhcp lease/i }).within(() =>
    cy
      .findByRole("button", { name: /reserve static dhcp lease/i })
      .last()
      .click()
  );

  cy.findByRole("complementary", { name: /reserve dhcp lease/i }).should(
    "not.exist",
    { timeout: LONG_TIMEOUT }
  );
});

Then(
  "the machine is linked to the static DHCP lease in the table",
  function () {
    cy.reload();
    cy.findByRole("table", { name: /static dhcp leases/i }).within(() => {
      cy.findByText(new RegExp(this.reservedMac, "i"))
        .closest("tr")
        .within(() => {
          cy.findByRole("link", {
            name: new RegExp(this.machineName, "i"),
          }).should("exist");
        });
    });
  }
);
