import DiskBootStatus from "./DiskBootStatus";

import { DiskTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("DiskBootStatus", () => {
  it("shows boot status for boot disks", () => {
    const disk = factory.nodeDisk({ is_boot: true, type: DiskTypes.PHYSICAL });
    renderWithProviders(<DiskBootStatus disk={disk} />);

    const icon = screen.getByLabelText("Boot disk");
    expect(icon).toHaveClass("p-icon--tick");
  });

  it("shows boot status for non-boot disks", () => {
    const disk = factory.nodeDisk({ is_boot: false, type: DiskTypes.PHYSICAL });
    renderWithProviders(<DiskBootStatus disk={disk} />);

    const icon = screen.getByLabelText("Non-boot disk");
    expect(icon).toHaveClass("p-icon--close");
  });

  it("shows boot status for non-physical disks", () => {
    const disk = factory.nodeDisk({ is_boot: false, type: DiskTypes.VIRTUAL });
    renderWithProviders(<DiskBootStatus disk={disk} />);

    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
