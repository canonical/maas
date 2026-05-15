export const expectCollapsedNavigation = () => {
  cy.getMainNavigation().invoke("width").should("equal", 64);
  cy.getMainNavigation().within(() =>
    cy.findByRole("link", { name: /machines/i }).should("not.exist")
  );
};
export const expectExpandedNavigation = () => {
  cy.getMainNavigation().invoke("width").should("equal", 240);
  cy.getMainNavigation().within(() =>
    cy.findByRole("link", { name: /machines/i }).should("exist")
  );
};
