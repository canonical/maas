import { Then, When } from "@badeball/cypress-cucumber-preprocessor";
import { LONG_TIMEOUT } from "../../../constants";

When("the user opens the first subnet", () => {
  cy.findByRole("grid", { name: "Subnets by fabric" }).within(() => {
    cy.get("tbody")
      .find('tr[class="p-generic-table__individual-row"]')
      .find("a")
      .first()
      .click();
  });
});

When("the user navigates to static routes", () => {
  cy.findByRole("heading", { level: 1 }).invoke("text").as("subnet");

  cy.findByRole("link", { name: /static routes/i }).click();
});

When("the user adds a static route", () => {
  cy.findByRole("button", { name: /add static route/i }).click();
  cy.get("@subnet").then((subnet: unknown) => {
    cy.findByRole("complementary", { name: /Add static route/i }).within(() => {
      const staticRoute = (subnet as string).split("/")[0];
      cy.wrap(staticRoute).as("staticRoute");
      cy.findByLabelText(/gateway ip/i).type(staticRoute);
      cy.findByLabelText(/destination/i).select(1);
    });
  });
  cy.findByRole("button", { name: /save/i }).click();
  cy.findByRole("complementary", { name: /Add static route/i }).should(
    "not.exist",
    { timeout: LONG_TIMEOUT }
  );
});

When("the user edits the static route", () => {
  cy.findByRole("region", { name: /Static routes/i }).within(() => {
    cy.get("tbody tr").first().findByRole("button", { name: /edit/i }).click();
  });

  cy.findByRole("complementary", { name: /Edit static route/i }).within(() => {
    cy.findByLabelText(/gateway ip/i).type("{Backspace}2");
    cy.findByRole("button", { name: /save/i }).click();
  });

  cy.get("@staticRoute").then((staticRoute: unknown) => {
    cy.findByRole("region", { name: /Static routes/i }).within(() => {
      const newStaticRoute = (staticRoute as string).slice(0, -1) + "2";
      cy.findByText(newStaticRoute);
    });
  });
  cy.findByRole("complementary", { name: /Edit static route/i }).should(
    "not.exist",
    { timeout: LONG_TIMEOUT }
  );
});

When("the user deletes the static route", () => {
  cy.findByRole("region", { name: /Static routes/i }).within(() => {
    cy.get("tbody tr")
      .first()
      .findByRole("button", { name: /delete/i })
      .click();
  });
});

Then("the static route should not exist", () => {
  cy.findByRole("complementary", { name: /Delete static route/i }).within(
    () => {
      cy.findByRole("button", { name: /delete/i }).click();
    }
  );
  cy.findByRole("complementary", {
    name: /Delete static route/i,
  }).should("not.exist", {
    timeout: LONG_TIMEOUT,
  });
  cy.get("@staticRoute").then((staticRoute: unknown) => {
    cy.findByRole("region", { name: /Static routes/i }).within(() => {
      cy.findByText(staticRoute as string).should("not.exist");
    });
  });
});
