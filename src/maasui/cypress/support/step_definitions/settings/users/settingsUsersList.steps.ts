import { Then } from "@badeball/cypress-cucumber-preprocessor";

Then(
  "the {string} side navigation item should be active",
  (heading: string) => {
    const navItem = ".p-side-navigation__link.is-active";
    cy.get(navItem).should("exist");
    cy.get(navItem).contains(heading);
  }
);
