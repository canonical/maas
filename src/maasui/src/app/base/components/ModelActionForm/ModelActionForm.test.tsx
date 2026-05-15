import ModelActionForm from "./ModelActionForm";

import { renderWithProviders, screen, userEvent } from "@/testing/utils";

it("renders", () => {
  renderWithProviders(
    <ModelActionForm
      initialValues={{}}
      modelType="machine"
      onSubmit={vi.fn()}
      submitLabel="Delete"
    />
  );
  expect(
    screen.getByText(
      "Are you sure you want to delete this machine? This action is permanent and cannot be undone."
    )
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
});

it("can confirm", async () => {
  const onSubmit = vi.fn();
  renderWithProviders(
    <ModelActionForm
      initialValues={{}}
      modelType="machine"
      onSubmit={onSubmit}
      submitLabel="Delete"
    />
  );
  const submitBtn = screen.getByRole("button", { name: /delete/i });
  await userEvent.click(submitBtn);
  expect(onSubmit).toHaveBeenCalled();
});

it("can cancel", async () => {
  const onCancel = vi.fn();
  renderWithProviders(
    <ModelActionForm
      cancelLabel="Cancel"
      initialValues={{}}
      modelType="machine"
      onCancel={onCancel}
      onSubmit={vi.fn()}
    />
  );
  const cancelBtn = screen.getByRole("button", { name: /cancel/i });
  await userEvent.click(cancelBtn);
  expect(onCancel).toHaveBeenCalled();
});
