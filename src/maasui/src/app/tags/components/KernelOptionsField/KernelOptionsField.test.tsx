import { Formik } from "formik";

import KernelOptionsField, { Label } from "./KernelOptionsField";

import { machineActions } from "@/app/store/machine";
import type { FetchFilters } from "@/app/store/machine/types";
import * as query from "@/app/store/machine/utils/query";
import type { RootState } from "@/app/store/root/types";
import { FetchNodeStatus, NodeStatus } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

let state: RootState;

beforeEach(() => {
  vi.spyOn(query, "generateCallId").mockReturnValueOnce("mocked-nanoid");
  state = factory.rootState({
    machine: factory.machineState({
      counts: factory.machineStateCounts({
        "mocked-nanoid": factory.machineStateCount({
          count: 1,
          loaded: true,
        }),
      }),
    }),
    tag: factory.tagState({
      items: [
        factory.tag({
          id: 1,
          name: "rad",
        }),
      ],
    }),
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

it("does not display a deployed machines message if a tag is not supplied", () => {
  renderWithProviders(
    <Formik initialValues={{}} onSubmit={vi.fn()}>
      <KernelOptionsField />
    </Formik>,
    { state }
  );
  expect(
    screen.queryByText(/The new kernel options will not be applied/i)
  ).not.toBeInTheDocument();
});

it("displays a deployed machines message when updating a tag", async () => {
  state = factory.rootState({
    machine: factory.machineState({
      items: [
        factory.machine({
          status: NodeStatus.DEPLOYED,
          tags: [1],
        }),
      ],
      counts: factory.machineStateCounts({
        "mocked-nanoid": factory.machineStateCount({
          count: 1,
          loaded: true,
          loading: false,
        }),
      }),
    }),
    tag: factory.tagState({
      items: [factory.tag({ id: 1, machine_count: 1 })],
    }),
  });

  renderWithProviders(
    <Formik initialValues={{}} onSubmit={vi.fn()}>
      <KernelOptionsField id={1} />
    </Formik>,
    { state }
  );
  await userEvent.type(
    screen.getByRole("textbox", { name: Label.KernelOptions }),
    "options2"
  );

  expect(
    screen.getByText(/There is 1 deployed machine with this tag./i)
  ).toBeInTheDocument();
  expect(
    screen.getByText(/The new kernel options will not be applied/i)
  ).toBeInTheDocument();
});

it("displays a deployed machines message when passed deployedMachinesCount", async () => {
  renderWithProviders(
    <Formik initialValues={{}} onSubmit={vi.fn()}>
      <KernelOptionsField deployedMachinesCount={1} />
    </Formik>,
    { state }
  );
  await userEvent.type(
    screen.getByRole("textbox", { name: Label.KernelOptions }),
    "options2"
  );
  expect(
    screen.getByText(/The new kernel options will not be applied/i)
  ).toBeInTheDocument();
});

it("fetches deployed machine count for selected tag when not passed deployedMachinesCount", async () => {
  const { store } = renderWithProviders(
    <Formik initialValues={{}} onSubmit={vi.fn()}>
      <KernelOptionsField id={state.tag.items[0].id} />
    </Formik>,
    { state }
  );
  const expected = machineActions.count("mocked-nanoid", {
    status: FetchNodeStatus.DEPLOYED,
    tags: [state.tag.items[0].name],
  } as FetchFilters);
  const actual = store
    .getActions()
    .find((action) => action.type === expected.type);
  expect(actual).toStrictEqual(expected);
  await userEvent.type(
    screen.getByRole("textbox", { name: Label.KernelOptions }),
    "options2"
  );
  expect(
    screen.getByText(/The new kernel options will not be applied/i)
  ).toBeInTheDocument();
});

it("can display a provided deployed machines message", async () => {
  renderWithProviders(
    <Formik initialValues={{}} onSubmit={vi.fn()}>
      <KernelOptionsField
        deployedMachinesCount={1}
        generateDeployedMessage={(count) => `${count} deployed machine`}
      />
    </Formik>,
    { state }
  );
  await userEvent.type(
    screen.getByRole("textbox", { name: Label.KernelOptions }),
    "options2"
  );
  expect(screen.getByText(/1 deployed machine/i)).toBeInTheDocument();
});
