import { Formik } from "formik";

import DefinitionField, { INVALID_XPATH_ERROR, Label } from "./DefinitionField";

import * as hooks from "@/app/base/hooks/analytics";
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

it("overrides the xpath errors", async () => {
  renderWithProviders(
    <Formik
      initialErrors={{
        definition: INVALID_XPATH_ERROR,
      }}
      initialValues={{}}
      onSubmit={vi.fn()}
    >
      <DefinitionField />
    </Formik>,
    { state }
  );
  expect(
    screen.getByRole("textbox", { name: Label.Definition })
  ).toHaveAccessibleErrorMessage(
    "The definition is an invalid XPath expression. See our XPath expressions documentation for more examples."
  );
});

it("displays a warning when changing the definition", async () => {
  state.tag.items[0].definition = "def1";
  renderWithProviders(
    <Formik
      initialErrors={{
        definition: INVALID_XPATH_ERROR,
      }}
      initialValues={{}}
      onSubmit={vi.fn()}
    >
      <DefinitionField id={1} />
    </Formik>,
    { state }
  );
  await userEvent.type(
    screen.getByRole("textbox", { name: Label.Definition }),
    "def2"
  );
  await waitFor(() => {
    expect(
      screen.getByText(/This tag will be unassigned/i)
    ).toBeInTheDocument();
  });
});

it("sends analytics when there is an xpath error", async () => {
  const mockSendAnalytics = vi.fn();
  vi.spyOn(hooks, "useSendAnalytics").mockImplementation(
    () => mockSendAnalytics
  );
  renderWithProviders(
    <Formik
      initialErrors={{
        definition: INVALID_XPATH_ERROR,
      }}
      initialValues={{}}
      onSubmit={vi.fn()}
    >
      <DefinitionField />
    </Formik>,
    { state }
  );
  expect(mockSendAnalytics).toHaveBeenCalled();
  expect(mockSendAnalytics.mock.calls[0]).toEqual([
    "XPath tagging",
    "Invalid XPath",
    "Save",
  ]);
});

// TODO: v2 state updates cannot be done without rerendering the component
//  and losing internal state, re-add this test when v3 is available
it.skip("does not send xpath error analytics more than once", async () => {
  const mockSendAnalytics = vi.fn();
  vi.spyOn(hooks, "useSendAnalytics").mockImplementation(
    () => mockSendAnalytics
  );
  const { rerender } = renderWithProviders(
    <Formik
      initialErrors={{
        definition: INVALID_XPATH_ERROR,
      }}
      initialValues={{}}
      onSubmit={vi.fn()}
    >
      <DefinitionField />
    </Formik>,
    { state }
  );

  rerender(
    <Formik
      initialErrors={{
        definition: INVALID_XPATH_ERROR,
      }}
      initialValues={{}}
      onSubmit={vi.fn()}
    >
      <DefinitionField />
    </Formik>,
    { state }
  );

  expect(mockSendAnalytics).toHaveBeenCalledTimes(1);
});
