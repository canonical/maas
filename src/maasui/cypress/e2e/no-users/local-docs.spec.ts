context("Local documentation", () => {
  beforeEach(() => {
    cy.visit(`${Cypress.env("BASENAME")}/docs`);
  });
  it("displays a correct heading", () => {
    cy.findByRole("heading", { name: /MAAS documentation/i }).should("exist");
  });
});
