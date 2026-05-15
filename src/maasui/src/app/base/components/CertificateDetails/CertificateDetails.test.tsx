import CertificateDetails, { Labels } from "./CertificateDetails";

import * as hooks from "@/app/base/hooks/analytics";
import { ConfigNames } from "@/app/store/config/types";
import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

describe("CertificateDetails", () => {
  it(`sends an analytics event when clicking the 'read more' link if analytics
    is enabled`, async () => {
    const mockSendAnalytics = vi.fn();
    const mockUseSendAnalytics = vi
      .spyOn(hooks, "useSendAnalytics")
      .mockImplementation(() => mockSendAnalytics);
    const state = factory.rootState({
      config: factory.configState({
        items: [
          factory.config({ name: ConfigNames.ENABLE_ANALYTICS, value: true }),
        ],
      }),
    });

    renderWithProviders(
      <CertificateDetails
        certificate="certificate"
        eventCategory="eventCategory"
        metadata={factory.certificateMetadata()}
      />,
      { state }
    );

    await userEvent.click(screen.getByRole("link", { name: Labels.ReadMore }));

    expect(mockSendAnalytics).toHaveBeenCalled();
    expect(mockSendAnalytics.mock.calls[0]).toEqual([
      "eventCategory",
      "Click link to LXD authentication discourse",
      "Read more about authentication",
    ]);
    mockUseSendAnalytics.mockRestore();
  });
});
