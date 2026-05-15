import DangerZoneCard from "./DangerZoneCard";

import DeleteForm from "@/app/kvm/components/DeleteForm";
import {
  mockSidePanel,
  screen,
  userEvent,
  renderWithProviders,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("DangerZoneCard", () => {
  it("can open the delete KVM form", async () => {
    renderWithProviders(<DangerZoneCard hostId={1} message="Delete KVM" />);
    await userEvent.click(screen.getByTestId("remove-kvm"));

    expect(mockOpen).toHaveBeenCalledWith({
      component: DeleteForm,
      title: "Delete KVM",
      props: {
        hostId: 1,
      },
    });
  });

  it("can display message", () => {
    renderWithProviders(
      <DangerZoneCard
        hostId={1}
        message={<span data-testid="message">Delete KVM</span>}
      />
    );
    expect(screen.getByTestId("message")).toHaveTextContent("Delete KVM");
  });
});
