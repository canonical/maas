import { Formik } from "formik";

import SpaceSelect from "./SpaceSelect";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  waitFor,
  renderWithProviders,
} from "@/testing/utils";

let state: RootState;

beforeEach(() => {
  state = factory.rootState({
    space: factory.spaceState({
      items: [],
      loaded: false,
    }),
  });
});

it("is disabled if spaces haven't loaded", () => {
  state.space.loaded = false;

  renderWithProviders(
    <Formik initialValues={{ space: "" }} onSubmit={vi.fn()}>
      <SpaceSelect name="space" />
    </Formik>,
    { state }
  );
  expect(screen.getByRole("combobox", { name: "Space" })).toBeDisabled();
  expect(
    screen.getByRole("option", { name: "Select space", selected: true })
  ).toBeDisabled();
});

it("renders options correctly", async () => {
  const space = factory.space({ id: 1, name: "space1" });
  state.space.items = [space];
  state.space.loaded = true;

  renderWithProviders(
    <Formik initialValues={{ space: "" }} onSubmit={vi.fn()}>
      <SpaceSelect name="space" />
    </Formik>,
    { state }
  );

  const allOptions: HTMLOptionElement[] = screen.getAllByRole("option");
  expect(allOptions).toHaveLength(2);

  const defaultOption = screen.getByRole("option", {
    name: "Select space",
    selected: true,
  });
  expect(defaultOption).toBeInTheDocument();
  expect(defaultOption).toBeDisabled();
  expect(defaultOption).toHaveValue("");

  const option = screen.getByRole("option", {
    name: space.name,
    selected: false,
  });
  expect(defaultOption).toBeInTheDocument();
  expect(option).not.toBeDisabled();
  expect(option).toHaveValue(space.id.toString());
});

it("maintains selected option after new options are added", async () => {
  const stateBefore = factory.rootState({
    space: factory.spaceState({
      items: [
        factory.space({ id: 1, name: "space1" }),
        factory.space({ id: 2, name: "space2" }),
        factory.space({ id: 3, name: "space3" }),
      ],
      loaded: true,
    }),
  });
  const stateAfter = factory.rootState({
    space: factory.spaceState({
      items: [
        factory.space({ id: 1, name: "space1" }),
        factory.space({ id: 2, name: "space2" }),
        factory.space({ id: 3, name: "space3" }),
        factory.space({ id: 4, name: "space4" }),
      ],
      loaded: true,
    }),
  });
  const { rerender } = renderWithProviders(
    <Formik initialValues={{ space: "" }} onSubmit={vi.fn()}>
      <SpaceSelect name="space" />
    </Formik>,
    { state: stateBefore }
  );

  await userEvent.selectOptions(screen.getByRole("combobox"), ["space2"]);
  const option2: HTMLOptionElement = screen.getByRole("option", {
    name: "space2",
  });

  await waitFor(() => {
    expect(option2.selected).toBe(true);
  });

  rerender(
    <Formik initialValues={{ space: "" }} onSubmit={vi.fn()}>
      <SpaceSelect name="space" />
    </Formik>,
    { state: stateAfter }
  );

  expect(option2.selected).toBe(true);
});

it("can hide the default option", () => {
  state.space.items = [];

  renderWithProviders(
    <Formik initialValues={{ space: "" }} onSubmit={vi.fn()}>
      <SpaceSelect defaultOption={null} name="space" />
    </Formik>,
    { state }
  );
  expect(screen.queryAllByRole("option")).toHaveLength(0);
});

it("orders the spaces by name", () => {
  state.space.items = [
    factory.space({ id: 1, name: "space3" }),
    factory.space({ id: 2, name: "space1" }),
  ];

  renderWithProviders(
    <Formik initialValues={{ space: "" }} onSubmit={vi.fn()}>
      <SpaceSelect name="space" />
    </Formik>,
    { state }
  );
  const options = screen.queryAllByRole("option");
  expect(options[0].textContent).toBe("Select space");
  expect(options[1].textContent).toBe("space1");
  expect(options[2].textContent).toBe("space3");
});
