import { Field, Formik } from "formik";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router";
import configureStore from "redux-mock-store";
import type { Mock } from "vitest";
import * as Yup from "yup";

import FormikFormContent from "./FormikFormContent";

import { TestIds } from "@/app/base/components/FormikFormButtons";
import * as hooks from "@/app/base/hooks/analytics";
import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  renderWithProviders,
  render,
} from "@/testing/utils";

const mockStore = configureStore<RootState>();

const mockUseNavigate = vi.fn();
vi.mock("react-router", async () => {
  const actual: object = await vi.importActual("react-router");
  return {
    ...actual,
    useNavigate: () => mockUseNavigate,
  };
});

describe("FormikFormContent", () => {
  let state: RootState;
  let scrollIntoViewSpy: Mock;

  beforeEach(() => {
    scrollIntoViewSpy = vi.fn();
    window.HTMLElement.prototype.scrollIntoView = scrollIntoViewSpy;

    state = factory.rootState({
      config: factory.configState({
        items: [
          factory.config({ name: ConfigNames.ENABLE_ANALYTICS, value: false }),
        ],
      }),
    });
  });

  afterEach(() => {
    vi.resetModules();
    vi.resetAllMocks();
  });

  it("disables cancel button while saving", () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <FormikFormContent onCancel={vi.fn()} saving>
          Content
        </FormikFormContent>
      </Formik>,
      { state }
    );

    expect(screen.getByTestId(TestIds.CancelButton)).toBeAriaDisabled();
  });

  it("can disable the submit button", async () => {
    const onSubmit = vi.fn();
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={onSubmit}>
        <FormikFormContent
          aria-label="example"
          submitDisabled
          submitLabel="Save"
        >
          Content
        </FormikFormContent>
      </Formik>,
      { state }
    );

    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("can override disabling cancel button while saving", () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <FormikFormContent cancelDisabled={false} onCancel={vi.fn()} saving>
          Content
        </FormikFormContent>
      </Formik>,
      { state }
    );

    expect(screen.getByTestId(TestIds.CancelButton)).not.toBeDisabled();
  });

  it("can display non-field errors from a string", () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <FormikFormContent errors="Uh oh!">Content</FormikFormContent>
      </Formik>,
      { state }
    );

    expect(screen.getByText("Uh oh!")).toBeInTheDocument();
  });

  it("scrolls non-field errors into view when present", () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <FormikFormContent errors="Uh oh!">Content</FormikFormContent>
      </Formik>,
      { state }
    );

    expect(screen.getByText("Uh oh!")).toBeInTheDocument();
    expect(scrollIntoViewSpy).toHaveBeenCalledTimes(1);
  });

  it("can display non-field errors from the __all__ key", () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <FormikFormContent errors={{ __all__: ["Uh oh!"] }}>
          Content
        </FormikFormContent>
      </Formik>,
      { state }
    );

    expect(screen.getByText("Uh oh!")).toBeInTheDocument();
  });

  it("can display non-field errors from the unknown keys with strings", () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <FormikFormContent errors={{ username: "Wrong username" }}>
          Content
        </FormikFormContent>
      </Formik>,
      { state }
    );

    expect(screen.getByText("Wrong username")).toBeInTheDocument();
  });

  it("does not display non-field errors for fields", () => {
    renderWithProviders(
      <Formik initialValues={{ username: "" }} onSubmit={vi.fn()}>
        <FormikFormContent errors={{ username: "Wrong username" }}>
          Content
        </FormikFormContent>
      </Formik>,
      { state }
    );

    expect(screen.queryByText("Wrong username")).not.toBeInTheDocument();
  });

  it("can display non-field errors from the unknown keys with arrays", () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <FormikFormContent
          errors={{
            username: ["Wrong username", "Username must be provided"],
          }}
        >
          Content
        </FormikFormContent>
      </Formik>,
      { state }
    );
    expect(
      screen.getByText("Wrong username, Username must be provided")
    ).toBeInTheDocument();
  });

  it("can display custom components for non-field errors", () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <FormikFormContent errors={<div>Errors component text</div>}>
          Content
        </FormikFormContent>
      </Formik>,
      { state }
    );

    expect(screen.getByText("Errors component text")).toBeInTheDocument();
  });

  it("can be inline", () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <FormikFormContent aria-label="Fake form" inline>
          Content
        </FormikFormContent>
      </Formik>,
      { state }
    );
    expect(screen.getByRole("form", { name: "Fake form" })).toHaveClass(
      "p-form--inline"
    );
  });

  it("does not render buttons if editable is set to false", () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <FormikFormContent editable={false}>Content</FormikFormContent>
      </Formik>,
      { state }
    );

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("can redirect when saved", () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <FormikFormContent saved={true} savedRedirect="/success">
          Content
        </FormikFormContent>
      </Formik>,
      { state }
    );

    expect(mockUseNavigate.mock.calls[0][0]).toBe("/success");
  });

  it("can clean up when unmounted", async () => {
    const cleanup = vi.fn(() => ({
      type: "CLEANUP",
    }));

    const {
      result: { unmount },
      store,
    } = renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <FormikFormContent cleanup={cleanup}>Content</FormikFormContent>
      </Formik>,
      { state }
    );

    unmount();

    expect(store.getActions()).toEqual([{ type: "CLEANUP" }]);
  });

  it("can send analytics when saved", () => {
    const eventData = {
      action: "Saved",
      category: "Settings",
      label: "Form",
    };
    const useSendMock = vi.spyOn(hooks, "useSendAnalyticsWhen");

    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <FormikFormContent
          onSaveAnalytics={eventData}
          saved={true}
          savedRedirect="/success"
        >
          Content
        </FormikFormContent>
      </Formik>,
      { state }
    );

    expect(useSendMock).toHaveBeenCalled();
    expect(useSendMock.mock.calls[0]).toEqual([
      true,
      eventData.category,
      eventData.action,
      eventData.label,
    ]);
    useSendMock.mockRestore();
  });

  it("can reset form on save if resetOnSave is true", async () => {
    const store = mockStore(state);
    const initialValues = {
      val1: "initial",
    };
    const Schema = Yup.object().shape({ val1: Yup.string() });

    // Proxy component required to be able to change FormikForm saved prop.
    const Proxy = ({ saved }: { saved: boolean }) => (
      <Provider store={store}>
        <MemoryRouter initialEntries={[{ pathname: "/", key: "testKey" }]}>
          <Formik
            initialValues={initialValues}
            onSubmit={vi.fn()}
            validationSchema={Schema}
          >
            <FormikFormContent resetOnSave saved={saved}>
              <Field name="val1" />
            </FormikFormContent>
          </Formik>
        </MemoryRouter>
      </Provider>
    );
    const { rerender } = render(<Proxy saved={false} />);
    const textbox = screen.getByRole("textbox");

    await userEvent.clear(textbox);
    await userEvent.type(textbox, "changed");
    expect(textbox).toHaveValue("changed");

    rerender(<Proxy saved={true} />);
    expect(textbox).toHaveValue("initial");
  });

  it("does not reset the form more than once", async () => {
    const store = mockStore(state);
    const initialValues = {
      val1: "initial",
    };
    const Schema = Yup.object().shape({ val1: Yup.string() });
    // Proxy component required to be able to change FormikForm saved prop.
    const Proxy = ({ saved }: { saved: boolean }) => (
      <Provider store={store}>
        <MemoryRouter initialEntries={[{ pathname: "/", key: "testKey" }]}>
          <Formik
            initialValues={initialValues}
            onSubmit={vi.fn()}
            validationSchema={Schema}
          >
            <FormikFormContent resetOnSave saved={saved}>
              <Field name="val1" />
            </FormikFormContent>
          </Formik>
        </MemoryRouter>
      </Provider>
    );
    const { rerender } = render(<Proxy saved={false} />);
    const textbox = screen.getByRole("textbox");

    await userEvent.clear(textbox);
    await userEvent.type(textbox, "changed");
    expect(textbox).toHaveValue("changed");

    rerender(<Proxy saved={true} />);
    expect(textbox).toHaveValue("initial");

    await userEvent.clear(textbox);
    await userEvent.type(textbox, "changed again");
    rerender(<Proxy saved={true} />);
    expect(textbox).toHaveValue("changed again");
  });

  it("runs onSuccess function if successfully saved with no errors", async () => {
    const onSuccess = vi.fn();
    const store = mockStore(state);
    const Proxy = ({ saved }: { saved: boolean }) => (
      <Provider store={store}>
        <MemoryRouter initialEntries={[{ pathname: "/", key: "testKey" }]}>
          <Formik initialValues={{}} onSubmit={vi.fn()}>
            <FormikFormContent onSuccess={onSuccess} saved={saved}>
              <Field name="val1" />
            </FormikFormContent>
          </Formik>
        </MemoryRouter>
      </Provider>
    );
    const { rerender } = render(<Proxy saved={false} />);
    expect(onSuccess).not.toHaveBeenCalled();

    rerender(<Proxy saved={true} />);
    expect(onSuccess).toHaveBeenCalled();
  });

  it("does not run onSuccess on first render", async () => {
    const onSuccess = vi.fn();
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <FormikFormContent errors={null} onSuccess={onSuccess} saved={true}>
          <Field name="val1" />
        </FormikFormContent>
      </Formik>,
      { state }
    );

    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("does not run onSuccess function if saved but there are errors", async () => {
    const onSuccess = vi.fn();

    const Proxy = ({ errors, saved }: { errors?: string; saved: boolean }) => (
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <FormikFormContent errors={errors} onSuccess={onSuccess} saved={saved}>
          <Field name="val1" />
        </FormikFormContent>
      </Formik>
    );
    const { rerender } = renderWithProviders(
      <Proxy errors={undefined} saved={false} />,
      {
        initialEntries: [{ pathname: "/", key: "testKey" }],
        state,
      }
    );
    expect(onSuccess).not.toHaveBeenCalled();

    rerender(<Proxy errors="Everything is ruined" saved={true} />);
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("does not run onSuccess function more than once", async () => {
    const onSuccess = vi.fn();
    const store = mockStore(state);
    const Proxy = ({
      saved,
      errors,
    }: {
      saved: boolean;
      errors?: string | null;
    }) => (
      <Provider store={store}>
        <MemoryRouter initialEntries={[{ pathname: "/", key: "testKey" }]}>
          <Formik initialValues={{}} onSubmit={vi.fn()}>
            <FormikFormContent
              errors={errors}
              onSuccess={onSuccess}
              saved={saved}
            >
              <Field name="val1" />
            </FormikFormContent>
          </Formik>
        </MemoryRouter>
      </Provider>
    );
    const { rerender } = render(<Proxy saved={false} />);
    rerender(<Proxy saved={true} />);
    expect(onSuccess).toHaveBeenCalledTimes(1);

    // Cycle the errors so that the success conditions are met again:
    rerender(<Proxy errors="Uh oh" saved={true} />);
    rerender(<Proxy errors={null} saved={true} />);
    expect(onSuccess).toHaveBeenCalledTimes(1);
  });

  it("can run onSuccess again after resetting the form", async () => {
    const onSuccess = vi.fn();
    const store = mockStore(state);
    const Proxy = ({
      saved,
      errors,
    }: {
      saved: boolean;
      errors?: string | null;
    }) => (
      <Provider store={store}>
        <MemoryRouter initialEntries={[{ pathname: "/", key: "testKey" }]}>
          <Formik initialValues={{}} onSubmit={vi.fn()}>
            <FormikFormContent
              errors={errors}
              onSuccess={onSuccess}
              resetOnSave
              saved={saved}
            >
              <Field name="val1" />
            </FormikFormContent>
          </Formik>
        </MemoryRouter>
      </Provider>
    );
    const { rerender } = render(<Proxy saved={false} />);

    rerender(<Proxy saved={true} />);
    expect(onSuccess).toHaveBeenCalledTimes(1);

    // Cycle the errors so that the success conditions are met again:
    rerender(<Proxy errors="Uh oh" saved={true} />);
    rerender(<Proxy errors={null} saved={true} />);
    expect(onSuccess).toHaveBeenCalledTimes(1);
  });

  it("can display a footer", () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <FormikFormContent
          footer={<div data-testid="footer"></div>}
          onCancel={vi.fn()}
        >
          Content
        </FormikFormContent>
      </Formik>,
      { state }
    );

    expect(screen.getByTestId("footer")).toBeInTheDocument();
  });

  it("renders inline form correctly when inline prop is true", () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <FormikFormContent aria-label="inline form" inline>
          <Field aria-label="test field" name="testField" />
        </FormikFormContent>
      </Formik>
    );

    expect(screen.getByRole("form", { name: "inline form" })).toHaveClass(
      "p-form--inline"
    );
    expect(
      screen.getByRole("textbox", { name: "test field" })
    ).toBeInTheDocument();
  });
});
