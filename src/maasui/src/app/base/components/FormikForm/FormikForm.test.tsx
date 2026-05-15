import FormikForm from "./FormikForm";

import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("FormikForm", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        items: [
          factory.config({ name: ConfigNames.ENABLE_ANALYTICS, value: false }),
        ],
      }),
    });
  });
  it("can render a form", () => {
    renderWithProviders(
      <FormikForm aria-label="example" initialValues={{}} onSubmit={vi.fn()}>
        Content
      </FormikForm>,
      { state }
    );
    expect(screen.getByRole("form", { name: "example" })).toBeInTheDocument();
  });
});
