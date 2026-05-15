import UpdateCertificate from "./UpdateCertificate";

import { generalActions } from "@/app/store/general";
import { podActions } from "@/app/store/pod";
import type { PodDetails } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("UpdateCertificate", () => {
  let state: RootState;
  let pod: PodDetails;

  beforeEach(() => {
    pod = factory.podDetails({ id: 1, name: "my-pod" });
    state = factory.rootState({
      general: factory.generalState({
        generatedCertificate: factory.generatedCertificateState({
          data: null,
        }),
      }),
      pod: factory.podState({
        items: [pod],
        loaded: true,
      }),
    });
  });

  it("can dispatch an action to generate certificate if not providing certificate and key", async () => {
    const { store } = renderWithProviders(
      <UpdateCertificate closeForm={vi.fn()} hasCertificateData pod={pod} />,
      { state }
    );

    // Radio should be set to generate certificate by default.
    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    const expectedAction = generalActions.generateCertificate({
      object_name: "my-pod",
    });
    const actualActions = store.getActions();
    expect(
      actualActions.find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });

  it("can generate a certificate with a custom object name", async () => {
    const { store } = renderWithProviders(
      <UpdateCertificate
        closeForm={vi.fn()}
        hasCertificateData
        objectName="custom-name"
        pod={pod}
      />,
      {
        state,
      }
    );
    // Radio should be set to generate certificate by default.
    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    const expectedAction = generalActions.generateCertificate({
      object_name: "custom-name",
    });
    const actualActions = store.getActions();
    expect(
      actualActions.find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });

  it("can dispatch an action to update pod with generated certificate and key", async () => {
    const generatedCertificate = factory.generatedCertificate({
      certificate: "generated-certificate",
      private_key: "private-key",
    });
    state.general.generatedCertificate.data = generatedCertificate;

    const { store } = renderWithProviders(
      <UpdateCertificate closeForm={vi.fn()} hasCertificateData pod={pod} />,
      {
        state,
      }
    );

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    const expectedAction = podActions.update({
      certificate: "generated-certificate",
      id: pod.id,
      key: "private-key",
      password: "",
      tags: pod.tags.join(","),
    });
    const actualActions = store.getActions();
    expect(
      actualActions.find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });

  it("can dispatch an action to update pod with provided certificate and key", async () => {
    const { store } = renderWithProviders(
      <UpdateCertificate closeForm={vi.fn()} hasCertificateData pod={pod} />,
      {
        state,
      }
    );

    // Change radio to provide certificate instead of generating one.
    const radio = screen.getByRole("radio", {
      name: "Provide certificate and private key",
    });
    await userEvent.click(radio);
    await userEvent.type(
      screen.getByRole("textbox", { name: "Upload certificate" }),
      "certificate"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Upload private key" }),
      "key"
    );
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    const expectedAction = podActions.update({
      certificate: "certificate",
      id: pod.id,
      key: "key",
      tags: pod.tags.join(","),
    });
    const actualActions = store.getActions();
    expect(
      actualActions.find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });

  it("closes the form on cancel if pod has a certificate", async () => {
    const closeForm = vi.fn();

    renderWithProviders(
      <UpdateCertificate closeForm={closeForm} hasCertificateData pod={pod} />,
      { state }
    );

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(closeForm).toHaveBeenCalled();
  });

  it(`clears generated certificate on cancel if pod has no certificate and a
      certificate has been generated`, async () => {
    const closeForm = vi.fn();
    state.general.generatedCertificate.data = factory.generatedCertificate();

    const { store } = renderWithProviders(
      <UpdateCertificate
        closeForm={closeForm}
        hasCertificateData={false}
        pod={pod}
      />,
      {
        state,
      }
    );
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    const expectedAction = generalActions.clearGeneratedCertificate();
    const actualAction = store
      .getActions()
      .find((action) => action.type === expectedAction.type);
    expect(actualAction).toStrictEqual(expectedAction);
  });

  it(`does not show a cancel button if pod has no certificate and no certificate
      has been generated`, () => {
    state.general.generatedCertificate.data = null;

    renderWithProviders(
      <UpdateCertificate
        closeForm={vi.fn()}
        hasCertificateData={false}
        pod={pod}
      />,
      {
        state,
      }
    );
    expect(
      screen.queryByRole("button", { name: "Cancel" })
    ).not.toBeInTheDocument();
  });
});
