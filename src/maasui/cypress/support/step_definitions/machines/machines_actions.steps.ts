import {
  Before,
  DataTable,
  Given,
  Then,
  When,
} from "@badeball/cypress-cucumber-preprocessor";
import { generateName } from "../../../e2e/utils";

let machineName = "";
let newPoolName = "";
let newTagName = "";
let doesMachineExist = false;

const openMachineActionDropdown = (groupLabel: string) => {
  cy.findAllByRole("button", { name: groupLabel }).first().click();
};

const openMachineActionForm = (groupLabel: string, action: string) => {
  openMachineActionDropdown(groupLabel);
  cy.findByLabelText(`${groupLabel} submenu`).within(() => {
    cy.findAllByRole("button", {
      name: new RegExp(`${action}...`),
    }).click();
  });
};

Before({ tags: "@machine-actions" }, () => {
  if (!doesMachineExist) {
    machineName = generateName("machine");
    cy.login();
    cy.addMachine(machineName);
    doesMachineExist = true;
  }
});

Given("the machines table is loaded", () => {
  cy.waitForTableToLoad({ name: /Machines/i });
});

Given("the user filters the machine list by the generated machine", () => {
  cy.findByRole("searchbox", { name: "Search" }).type(machineName);
  cy.waitForTableToLoad({ name: /Machines/i });
});

Given("the user selects that machine", () => {
  cy.findByRole("checkbox", {
    name: `${machineName}.maas`,
  }).click({ force: true });
});

When("the user selects the first machine in the grid", () => {
  cy.findByRole("grid", { name: /Machines/i }).within(() => {
    cy.findAllByRole("gridcell", { name: /FQDN/i })
      .first()
      .within(() => {
        cy.findByRole("checkbox").click({ force: true });
      });
  });
});

When(
  "the user opens the {string} form from the {string} menu",
  (action: string, group: string) => {
    openMachineActionForm(group, action);
  }
);
When("the user cancels the {string} form", (formName: string) => {
  cy.findByRole("complementary", { name: new RegExp(formName, "i") }).within(
    () => {
      cy.findByRole("button", { name: /Cancel/i }).click();
    }
  );
});

When("the user creates a new pool", () => {
  newPoolName = generateName("pool");
  cy.findByRole("complementary", { name: /Set pool/i }).should("exist");
  cy.findByLabelText(/Create pool/i).click({ force: true });
  cy.findByLabelText(/Name/i).type(newPoolName);
});

When("the user creates a new tag", () => {
  newTagName = generateName("tag");
  cy.findByRole("complementary", { name: /Tag/i }).should("exist");

  cy.findByRole("textbox", {
    name: "Search existing or add new tags",
  }).type(newTagName);

  cy.findByRole("button", { name: `Create tag "${newTagName}"` }).click();
  cy.findByRole("form", { name: /Create tag/i }).should("be.visible");
  cy.findByRole("button", {
    name: /Create and add to tag changes/i,
  }).click();
});

Then("the following action groups should be available:", (table: DataTable) => {
  const rows = table.hashes() as Array<{ group: string; actions: string }>;

  rows.forEach(({ group, actions }) => {
    const expectedActions = actions.split(",").map((action) => action.trim());

    openMachineActionDropdown(group);

    cy.findByLabelText(`${group} submenu`).within(() => {
      cy.findAllByRole("button").should("have.length", expectedActions.length);
      cy.findAllByRole("button").should("be.enabled");
    });
  });
});

Then("the {string} action should be enabled", (action: string) => {
  cy.findByRole("button", { name: new RegExp(action, "i") })
    .should("exist")
    .and("be.enabled");
});

Then("the {string} side panel should be visible", (panelName: string) => {
  cy.findByRole("complementary", { name: new RegExp(panelName, "i") }).within(
    () => {
      cy.findAllByText(/Loading/i).should("have.length", 0);
      cy.findByRole("heading", { name: new RegExp(panelName, "i") }).should(
        "exist"
      );
    }
  );
});

Then("the {string} side panel should not exist", (panelName: string) => {
  cy.findByRole("complementary", { name: new RegExp(panelName, "i") }).should(
    "not.exist"
  );
});

Then("the new pool name should be visible in the machines grid", () => {
  cy.findByRole("grid", { name: /Machines/i }).within(() => {
    cy.findByText(newPoolName).should("exist");
  });
});

Then(
  "the {string} table should contain the new tag marked {string}",
  (tableName: string, status: string) => {
    cy.findByRole("table", { name: new RegExp(tableName, "i") }).within(() => {
      cy.findByRole("cell", { name: new RegExp(status, "i") }).should("exist");
      cy.findByRole("cell", { name: new RegExp(newTagName, "i") }).should(
        "exist"
      );
    });
  }
);

Then("the new tag should be visible in the machines grid", () => {
  cy.findByRole("grid", { name: /Machines/i }).within(() => {
    cy.findByText(newTagName).should("exist");
  });
});
