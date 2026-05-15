import {
  After,
  Before,
  Given,
  Then,
  When,
} from "@badeball/cypress-cucumber-preprocessor";
import { LONG_TIMEOUT } from "../../../constants";
import { generateMAASURL, generateName } from "../../../e2e/utils";

const GROUP_BY_OPTIONS = [
  "No grouping",
  "Group by status",
  "Group by owner",
  "Group by resource pool",
  "Group by architecture",
  "Group by domain",
  "Group by parent",
  "Group by KVM",
  "Group by KVM type",
  "Group by power state",
  "Group by zone",
] as const;

type ScenarioState = {
  generatedName?: string;
  generatedMachines?: string[];
  searchFilter?: string;
  initialPage?: string;
};

let state: ScenarioState;

const getGroupBySelect = () => cy.findByRole("combobox", { name: "Group by" });

Before({ tags: "@machine-list" }, () => {
  state = {};
});

After({ tags: "@machine-list" }, () => {
  cy.window().then((win) => {
    win.localStorage.removeItem("grouping");
  });
});

Given("all options of grouping are available", () => {
  getGroupBySelect().within(() => {
    cy.findAllByRole("option").should("have.length", GROUP_BY_OPTIONS.length);
  });
});

Given("there are commissioning machines matching a generated hostname", () => {
  const name = generateName();
  const machines = [`${name}-1`, `${name}-2`];
  const searchFilter = `status:(=commissioning) hostname:(${name})`;

  state.generatedName = name;
  state.generatedMachines = machines;
  state.searchFilter = searchFilter;

  cy.findByRole("searchbox").type(searchFilter);
  cy.findByText(/No machines match the search criteria./, {
    timeout: LONG_TIMEOUT,
  }).should("exist");

  cy.addMachines(machines);
});

Given("the user has visited the network discovery page", () => {
  const initialPage = generateMAASURL("/network-discovery");
  state.initialPage = initialPage;
  cy.visit(initialPage);
});

Given("initial state of the page is correct", () => {
  cy.findByRole("searchbox").should("have.value", "");
  cy.findByRole("link", { name: /[0-9]+ pool[s]?/i }).should("exist");
});

Given(
  'the user opens the machines page with the "new" status filter in the URL',
  () => {
    cy.visit(generateMAASURL("/machines?status=%3Dnew"));
  }
);

Given("three generated machines exist", () => {
  const name = generateName();
  const machines = [`${name}-a`, `${name}-b`, `${name}-c`];

  state.generatedName = name;
  state.generatedMachines = machines;

  cy.addMachines(machines);
});

Given("the user disables grouping", () => {
  cy.findByRole("combobox", { name: "Group by" }).select("No grouping");
});

Given("the user filters by the generated machine prefix", () => {
  if (!state.generatedName) {
    throw new Error("generatedName was not initialized");
  }
  cy.findByRole("searchbox", { name: "Search" }).type(state.generatedName);
});

Given("a pools link should be visible", () => {
  cy.findByRole("link", { name: /[0-9]+ pool[s]?/i }).should("exist");
});

Given("the {string} link should not be visible", (linkName: string) => {
  cy.findByRole("link", { name: linkName }).should("not.exist");
});

When(
  "the user selects {string} from the group by dropdown",
  (groupBy: string) => {
    getGroupBySelect().select(groupBy);
  }
);

When("the user groups machines by status", () => {
  getGroupBySelect().select("Group by status");
});

When(
  "the user filters machines by the generated hostname and commissioning status",
  () => {
    if (!state.searchFilter) {
      throw new Error("searchFilter was not initialized");
    }

    cy.findByRole("searchbox").clear().type(state.searchFilter);
  }
);

When("the user selects the commissioning group", () => {
  cy.findByRole("grid", { name: /Machines/ }).within(() => {
    cy.findByRole("checkbox", { name: /Commissioning/i }).click({
      force: true,
    });
  });
});

When("the user deletes the selected machines", () => {
  cy.findByRole("button", { name: /Delete/i }).click();

  if (state.generatedMachines?.length === 3) {
    cy.findByRole("button", { name: /Delete 3 machines/i }).click();
    return;
  }

  if (state.generatedMachines?.length === 2) {
    cy.findByRole("button", { name: /Delete 2 machines/i }).should("exist");
    cy.findByRole("button", { name: /Delete 2 machines/i }).click();
    return;
  }

  throw new Error("Could not determine how many machines should be deleted");
});

When("the user selects the {string} filter tab", (tabName: string) => {
  cy.findByRole("tab", { name: new RegExp(tabName, "i") })
    .should("exist")
    .click();
});

When("the user enables the {string} filter", (filterName: string) => {
  cy.findByRole("checkbox", { name: filterName }).should("exist").click();
});

When("the user enables the filter matching {string}", (filterName: string) => {
  cy.findByRole("checkbox", { name: new RegExp(filterName, "i") })
    .should("exist")
    .click();
});

When("the user navigates back", () => {
  cy.go("back");
});

When("the user navigates forward", () => {
  cy.go("forward");
});

When("the user hides the {string} column", (columnName: string) => {
  cy.findByLabelText("columns menu").within(() => {
    cy.findByRole("checkbox", { name: columnName }).click({ force: true });
  });
});

When("the user selects the first machine", () => {
  const firstMachine = state.generatedMachines?.[0];

  if (!firstMachine) {
    throw new Error("First generated machine was not initialized");
  }

  cy.findByRole("checkbox", { name: `${firstMachine}.maas` }).click({
    force: true,
  });
});

When("the user shift-selects the third machine", () => {
  const thirdMachine = state.generatedMachines?.[2];

  if (!thirdMachine) {
    throw new Error("Third generated machine was not initialized");
  }

  cy.findByRole("checkbox", { name: `${thirdMachine}.maas` }).click({
    shiftKey: true,
    force: true,
  });
});

Then("the machine list heading should be visible", () => {
  cy.findByRole("heading", {
    name: /[0-9]+ machine[s]? in [0-9]+ pool[s]?/i,
  }).should("exist");
});

Then("the machines grid for {string} should exist", (groupBy: string) => {
  cy.findByRole("grid", { name: `Machines - ${groupBy}` }).should("exist");
});

Then("the text {string} should be visible", (text: string) => {
  cy.findByText(text).should("exist");
});

Then(
  "the delete 2 machines confirmation should be handled successfully",
  () => {
    if (!state.searchFilter) {
      throw new Error("searchFilter was not initialized");
    }

    cy.findByRole("searchbox").clear().type(state.searchFilter);
    cy.findByText(/No machines match the search criteria./, {
      timeout: LONG_TIMEOUT,
    }).should("exist");
  }
);

Then("the machine searchbox should contain {string}", (value: string) => {
  cy.findByRole("searchbox").should("have.value", value);
});

Then("the machine URL should contain the testing status filter", () => {
  cy.findByRole("searchbox").should("have.value", "status:(=testing)");
  cy.location().should((loc) => {
    expect(loc.search).to.eq("?status=%3Dtesting");
    expect(loc.pathname).to.eq(generateMAASURL("/machines"));
  });
});

Then("the user should be on the network discovery page", () => {
  if (!state.initialPage) {
    throw new Error("initialPage was not initialized");
  }

  cy.location().should((loc) => {
    expect(loc.search).to.eq("");
    expect(loc.pathname).to.eq(state.initialPage);
  });
});

Then("the machine table should show {int} columns", (count: number) => {
  cy.findAllByRole("columnheader").should("have.length", count);
});

Then("the second machine should be selected", () => {
  const secondMachine = state.generatedMachines?.[1];

  if (!secondMachine) {
    throw new Error("Second generated machine was not initialized");
  }

  cy.findByRole("checkbox", { name: `${secondMachine}.maas` }).should(
    "be.checked"
  );
});

Then("the {string} filter should be visible", (filterName: string) => {
  cy.findByRole("checkbox", { name: new RegExp(filterName, "i") }).should(
    "exist"
  );
});
