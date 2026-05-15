import { Then, When } from "@badeball/cypress-cucumber-preprocessor";
import { LONG_TIMEOUT, VERY_LONG_TIMEOUT } from "../../../constants";
import { findRow } from "../common/table_actions.steps";

let selectedImageId = "";

When("the user opens the {string} release dropdown", (release: string) => {
  const hasSelectors = release
    .split(/\s+/)
    .map((part) => `:has(:contains("${part}"))`)
    .join("");
  cy.findByRole("complementary", { name: "Select upstream images to sync" })
    .find(`tr${hasSelectors}`)
    .first()
    .then(($row) => {
      const title = $row.find("td:first-of-type div div").first().text().trim();
      const codename = $row.find("td:first-of-type small").text().trim();
      selectedImageId = [title, codename].filter(Boolean).join(" ");
    })
    .findByRole("combobox")
    .click();
});

When("the user selects and captures the first available option", () => {
  cy.get(".multi-select__dropdown")
    .find(".p-checkbox__label")
    .first()
    .then(($label) => {
      selectedImageId = `${selectedImageId} ${$label.text().trim()}`;
    })
    .click();
});

Then(
  "the selected image row should show {string} in the table",
  (status: string) => {
    findRow(selectedImageId, LONG_TIMEOUT).within(() => {
      cy.contains(status).should("exist");
    });
  }
);

Then(
  "the {string} row action for the selected image row should be enabled",
  (action: string) => {
    findRow(selectedImageId)
      .findByRole("button", { name: action, timeout: VERY_LONG_TIMEOUT })
      .should("not.have.attr", "aria-disabled", "true");
  }
);

When(
  "the user clicks the {string} row action for the selected image row",
  (action: string) => {
    findRow(selectedImageId).findByRole("button", { name: action }).click();
  }
);

Then("the selected image row should not be visible in the table", () => {
  findRow(selectedImageId, LONG_TIMEOUT).should("not.exist");
});
