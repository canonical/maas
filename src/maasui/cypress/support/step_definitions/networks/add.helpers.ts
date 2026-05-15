export const openAddForm = (name: string) => {
  cy.findByRole("button", { name: "Add" }).click();
  cy.findByRole("button", { name }).click();
};

export const submitForm = (formName: string) => {
  cy.findByRole("button", {
    name: new RegExp(String.raw`Save ${formName}`, "i"),
  }).click();
};

export const completeAddVlanForm = (
  vid: string,
  name: string,
  fabricName?: string,
  spaceName?: string
) => {
  openAddForm("VLAN");
  cy.findByRole("textbox", { name: "VID" }).type(vid);
  cy.findByRole("combobox", { name: "Fabric" }).select(fabricName || 1);
  if (spaceName) {
    cy.findByRole("combobox", { name: "Space" }).select(spaceName);
  }
  cy.findByRole("textbox", { name: "Name" }).type(name);
  cy.findByRole("button", { name: "Save VLAN" }).click();
};

export const completeForm = (formName: string, name: string) => {
  openAddForm(formName);
  cy.findByRole("textbox", { name: "Name (optional)" }).type(name);
  submitForm(formName);
};
