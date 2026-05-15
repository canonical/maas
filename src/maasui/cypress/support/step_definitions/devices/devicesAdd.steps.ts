import { Then, When } from "@badeball/cypress-cucumber-preprocessor";
import { generateMac, generateName } from "../../../e2e/utils";

let deviceName = "";

When("the user enters valid device details", () => {
  deviceName = generateName("device");
  Cypress.env("createdDeviceName", deviceName);

  cy.findByLabelText(/Device name/).type(deviceName);
  cy.get("input[placeholder='00:00:00:00:00:00']").type(generateMac());

  const shouldUseKnownIp = !!Cypress.env("useKnownDeviceIpForDnsRecordTest");
  if (shouldUseKnownIp) {
    const knownSubnetCidr = String(Cypress.env("knownSubnetCidr") || "");
    const knownDeviceIp = String(Cypress.env("knownDeviceIp") || "");

    expect(knownSubnetCidr, "known subnet CIDR").to.not.equal("");
    expect(knownDeviceIp, "known device IP").to.not.equal("");

    cy.findByRole("combobox", { name: /IP assignment/i }).select(
      "Static (Client configured)"
    );

    cy.findByRole("combobox", { name: /Subnet/i })
      .find("option")
      .then(($options) => {
        const matchingOption = [...$options].find((option) =>
          option.textContent?.includes(knownSubnetCidr)
        );
        const subnetValue = matchingOption?.getAttribute("value") || "";
        cy.findByRole("combobox", { name: /Subnet/i }).select(subnetValue);
      });

    const suffix = knownDeviceIp.split(".").pop() || knownDeviceIp;
    cy.findByRole("textbox", { name: /IP address/i }).type(suffix);

    Cypress.env("useKnownDeviceIpForDnsRecordTest", false);
  }
});

Then("the new device should appear in the device list", () => {
  cy.findByRole("link", { name: new RegExp(deviceName, "i") }).should("exist");
});
