import { After, Then, When } from "@badeball/cypress-cucumber-preprocessor";

let kernelParameters = "";

const getSaveButton = () => cy.findByRole("button", { name: /Save/i });

const getKernelParamsInput = () =>
  cy.findByLabelText(/Global boot parameters always passed to the kernel/i);

After({ tags: "@kernel-parameters-cleanup" }, () => {
  getKernelParamsInput().clear();
  getSaveButton().click();
  getSaveButton().should("be.disabled");
});

When("the user clears the kernel parameters field", () => {
  getKernelParamsInput().clear();
});

When("the user enters the new kernel parameters", () => {
  kernelParameters = "sysrq_always_enabled dyndbg='file drivers/usb/*";
  getKernelParamsInput().type(kernelParameters);
});

When("the user saves the kernel parameters", () => {
  getSaveButton().click();
});

Then("the save button should be disabled", () => {
  getSaveButton().should("be.disabled");
});

Then("the kernel parameters field should have the updated value", () => {
  getKernelParamsInput().should("have.value", kernelParameters);
});
