import { Formik } from "formik";

import type { FormValues } from "../EditBootArchitectures";

import BootArchitecturesTable from "./BootArchitecturesTable";

import * as factory from "@/testing/factories";
import { renderWithProviders, screen, within } from "@/testing/utils";

let initialValues: FormValues;

beforeEach(() => {
  initialValues = {
    disabled_boot_architectures: [],
  };
});

it("renders a table of known boot architectures", () => {
  const knownBootArchitecture = factory.knownBootArchitecture();
  const state = factory.rootState({
    general: factory.generalState({
      knownBootArchitectures: factory.knownBootArchitecturesState({
        data: [knownBootArchitecture],
      }),
    }),
  });
  renderWithProviders(
    <Formik initialValues={initialValues} onSubmit={vi.fn()}>
      <BootArchitecturesTable />
    </Formik>,
    { state }
  );

  const rows = within(screen.getAllByRole("rowgroup")[1]).getAllByRole("row");
  const firstRowCells = within(rows[0]).getAllByRole("cell");

  expect(firstRowCells[0]).toHaveTextContent(knownBootArchitecture.name);
  expect(firstRowCells[1]).toHaveTextContent(
    knownBootArchitecture.bios_boot_method
  );
  expect(firstRowCells[2]).toHaveTextContent(
    knownBootArchitecture.bootloader_arches
  );
  expect(firstRowCells[3]).toHaveTextContent(knownBootArchitecture.protocol);
  expect(firstRowCells[4]).toHaveTextContent(
    `${knownBootArchitecture.arch_octet}`
  );
});

it("renders a '—' if bootloader_arches or arch_octect are empty", () => {
  const knownBootArchitecture = factory.knownBootArchitecture({
    bootloader_arches: "",
    arch_octet: null,
  });
  const state = factory.rootState({
    general: factory.generalState({
      knownBootArchitectures: factory.knownBootArchitecturesState({
        data: [knownBootArchitecture],
      }),
    }),
  });
  renderWithProviders(
    <Formik initialValues={initialValues} onSubmit={vi.fn()}>
      <BootArchitecturesTable />
    </Formik>,
    { state }
  );

  const rows = within(screen.getAllByRole("rowgroup")[1]).getAllByRole("row");
  const firstRowCells = within(rows[0]).getAllByRole("cell");

  expect(firstRowCells[2]).toHaveTextContent("—");
  expect(firstRowCells[4]).toHaveTextContent("—");
});

it("sorts by name by default", () => {
  const knownBootArchitectures = [
    factory.knownBootArchitecture({ name: "a-arch" }),
    factory.knownBootArchitecture({ name: "b-arch" }),
    factory.knownBootArchitecture({ name: "c-arch" }),
  ];
  const state = factory.rootState({
    general: factory.generalState({
      knownBootArchitectures: factory.knownBootArchitecturesState({
        data: knownBootArchitectures,
      }),
    }),
  });
  renderWithProviders(
    <Formik initialValues={initialValues} onSubmit={vi.fn()}>
      <BootArchitecturesTable />
    </Formik>,
    { state }
  );

  const rows = within(screen.getAllByRole("rowgroup")[1]).getAllByRole("row");

  expect(within(rows[0]).getAllByRole("cell")[0]).toHaveTextContent(
    knownBootArchitectures[0].name
  );
  expect(within(rows[1]).getAllByRole("cell")[0]).toHaveTextContent(
    knownBootArchitectures[1].name
  );
  expect(within(rows[2]).getAllByRole("cell")[0]).toHaveTextContent(
    knownBootArchitectures[2].name
  );
});

it("unchecks disabled architectures", () => {
  initialValues = {
    disabled_boot_architectures: ["i386"],
  };

  const knownBootArchitectures = [
    factory.knownBootArchitecture({ name: "amd64" }),
    factory.knownBootArchitecture({ name: "i386" }),
  ];
  const state = factory.rootState({
    general: factory.generalState({
      knownBootArchitectures: factory.knownBootArchitecturesState({
        data: knownBootArchitectures,
      }),
    }),
  });
  renderWithProviders(
    <Formik initialValues={initialValues} onSubmit={vi.fn()}>
      <BootArchitecturesTable />
    </Formik>,
    { state }
  );

  expect(screen.getByRole("checkbox", { name: "amd64" })).toBeChecked();
  expect(screen.getByRole("checkbox", { name: "i386" })).not.toBeChecked();
});
