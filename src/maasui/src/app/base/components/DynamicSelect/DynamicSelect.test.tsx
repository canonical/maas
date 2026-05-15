import { Formik } from "formik";

import DynamicSelect from "./DynamicSelect";
import type { Props as DynamicSelectProps } from "./DynamicSelect";

import {
  userEvent,
  fireEvent,
  render,
  screen,
  waitFor,
  renderWithProviders,
} from "@/testing/utils";

describe("DynamicSelect", () => {
  it("resets to the first option if the options change and the value no longer exists", async () => {
    const MockComponent = (props: DynamicSelectProps) => (
      <Formik initialValues={{ fabric: "" }} onSubmit={vi.fn()}>
        <DynamicSelect {...props} />
      </Formik>
    );
    const { rerender } = render(
      <MockComponent
        name="fabric"
        options={[
          { label: "one", value: "1" },
          { label: "two", value: "2" },
        ]}
      />
    );
    const select = screen.getByRole("combobox");

    await userEvent.selectOptions(select, "2");
    expect(select).toHaveValue("2");

    rerender(
      <MockComponent
        name="fabric"
        options={[
          { label: "three", value: "3" },
          { label: "four", value: "4" },
        ]}
      />
    );
    expect(select).toHaveValue("3");
  });

  it("doesn't change the value if the options change and the value still exists", async () => {
    const MockComponent = (props: DynamicSelectProps) => (
      <Formik initialValues={{ fabric: "" }} onSubmit={vi.fn()}>
        <DynamicSelect {...props} />
      </Formik>
    );
    const { rerender } = render(
      <MockComponent
        name="fabric"
        options={[
          { label: "one", value: "1" },
          { label: "two", value: "2" },
        ]}
      />
    );
    const select = screen.getByRole("combobox");

    await userEvent.selectOptions(select, "2");
    expect(select).toHaveValue("2");

    rerender(
      <MockComponent
        name="fabric"
        options={[
          { label: "two", value: "2" },
          { label: "three", value: "3" },
        ]}
      />
    );
    expect(select).toHaveValue("2");
  });

  it("accepts changing to a value that is a number", async () => {
    renderWithProviders(
      <Formik initialValues={{ fabric: "" }} onSubmit={vi.fn()}>
        <DynamicSelect
          name="fabric"
          options={[
            { label: "one", value: "1" },
            { label: "two", value: "2" },
          ]}
        />
      </Formik>
    );
    const select = screen.getByRole("combobox");

    fireEvent.change(select, { target: { name: "fabric", value: 2 } });
    await waitFor(() => {
      expect(select).toHaveValue("2");
    });
  });

  it("accepts updated values that are numbers", async () => {
    const MockComponent = (props: DynamicSelectProps) => (
      <Formik initialValues={{ fabric: "" }} onSubmit={vi.fn()}>
        <DynamicSelect {...props} />
      </Formik>
    );
    const { rerender } = render(
      <MockComponent
        name="fabric"
        options={[
          { label: "one", value: "1" },
          { label: "two", value: "2" },
        ]}
      />
    );
    const select = screen.getByRole("combobox");

    await userEvent.selectOptions(select, "2");
    expect(select).toHaveValue("2");

    rerender(
      <MockComponent
        name="fabric"
        options={[
          { label: "one", value: 1 },
          { label: "two", value: 2 },
        ]}
      />
    );
    expect(select).toHaveValue("2");
  });

  it("doesn't change the value on first render", async () => {
    renderWithProviders(
      <Formik initialValues={{ fabric: "2" }} onSubmit={vi.fn()}>
        <DynamicSelect
          name="fabric"
          options={[
            { label: "one", value: "1" },
            { label: "two", value: "2" },
          ]}
        />
      </Formik>
    );
    const select = screen.getByRole("combobox");

    expect(select).toHaveValue("2");
  });
});
