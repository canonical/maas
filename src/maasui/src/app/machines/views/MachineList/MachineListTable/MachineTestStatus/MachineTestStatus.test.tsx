import MachineTestStatus from "./MachineTestStatus";

import { TestStatusStatus } from "@/app/store/types/node";
import { screen, userEvent, renderWithProviders } from "@/testing/utils";

describe("MachineTestStatus", () => {
  it("renders", () => {
    renderWithProviders(
      <MachineTestStatus status={TestStatusStatus.PENDING}>
        Tests are pending
      </MachineTestStatus>
    );
    expect(screen.getByText(/Tests are pending/i)).toBeInTheDocument();
  });

  it("does not display an icon if tests have passed", () => {
    renderWithProviders(
      <MachineTestStatus status={TestStatusStatus.PASSED}>
        Tests have passed
      </MachineTestStatus>
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("shows a failed icon with tooltip if tests have failed", async () => {
    renderWithProviders(
      <MachineTestStatus status={TestStatusStatus.FAILED}>
        Tests have failed
      </MachineTestStatus>
    );
    expect(screen.getByRole("button").querySelector("i")).toHaveClass(
      "p-icon--error"
    );
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByText(/Machine has failed tests./i)).toBeInTheDocument();
  });
});
