import { generateMAASURL } from "../utils";

context("Google Analytics", () => {
  beforeEach(function () {
    const gtag = cy.stub().as("gtag");
    cy.intercept({ hostname: "www.google-analytics.com" }, { statusCode: 503 });
    Cypress.on("window:before:load", (win) => {
      Object.defineProperty(win, "gtag", {
        configurable: false,
        get: () => gtag,
        set: () => {},
      });
    });
    cy.login();
  });

  it("window.gtag is called correctly", function () {
    cy.visit(generateMAASURL("/machines"));
    cy.get("@gtag")
      // ensure GA was created with our google analytics ID
      .should("be.calledWith", "create", "UA-1018242-63")
      // ensure that the initial pageview is sent
      .and("be.calledWith", "send", "pageview", "machines");

    cy.visit(generateMAASURL("/devices"));
    cy.get("@gtag").and("be.calledWith", "send", "pageview", "devices");
  });
});
