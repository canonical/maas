import { generateMAASURL } from "../utils";

context("Login without users", () => {
  it("shows a create admin message", () => {
    cy.visit(generateMAASURL("/"));
    cy.get(".p-card__title").contains("No admin user has been created yet");
  });
});
