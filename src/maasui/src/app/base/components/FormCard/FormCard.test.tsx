import FormCard, { TestIds } from "./FormCard";

import { COL_SIZES } from "@/app/base/constants";
import { screen, renderWithProviders } from "@/testing/utils";

const { CARD_TITLE, SIDEBAR, TOTAL } = COL_SIZES;

describe("FormCard ", () => {
  it("can display the heading on a separate row", () => {
    renderWithProviders(
      <FormCard stacked title="Add user">
        Content
      </FormCard>
    );
    expect(screen.queryByTestId(TestIds.ColContent)).not.toBeInTheDocument();
  });

  it("occupies full width if neither sidebar or title is present", () => {
    renderWithProviders(
      <FormCard sidebar={false} title={null}>
        Content
      </FormCard>
    );

    expect(screen.getByTestId(TestIds.ColContent)).toHaveClass(`col-${TOTAL}`);
  });

  it("decreases column size if title is presnet", () => {
    renderWithProviders(
      <FormCard sidebar={false} title="Title">
        Content
      </FormCard>
    );

    expect(screen.getByTestId(TestIds.ColContent)).toHaveClass(
      `col-${TOTAL - CARD_TITLE}`
    );
  });

  it("decreases column size if sidebar is presnet", () => {
    renderWithProviders(
      <FormCard sidebar title={null}>
        Content
      </FormCard>
    );

    expect(screen.getByTestId(TestIds.ColContent)).toHaveClass(
      `col-${TOTAL - SIDEBAR}`
    );
  });

  it("decreases column size if title and sidebar are present", () => {
    renderWithProviders(
      <FormCard sidebar title="Title">
        Content
      </FormCard>
    );

    expect(screen.getByTestId(TestIds.ColContent)).toHaveClass(
      `col-${TOTAL - CARD_TITLE - SIDEBAR}`
    );
  });
});
