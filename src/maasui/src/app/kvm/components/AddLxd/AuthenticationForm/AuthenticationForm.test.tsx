import { AddLxdSteps } from "../AddLxd";
import type { NewPodValues } from "../types";

import AuthenticationForm from "./AuthenticationForm";

import { generalActions } from "@/app/store/general";
import { podActions } from "@/app/store/pod";
import { PodType } from "@/app/store/pod/constants";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("AuthenticationForm", () => {
  let state: RootState;
  let newPodValues: NewPodValues;

  beforeEach(() => {
    state = factory.rootState({
      general: factory.generalState({
        generatedCertificate: factory.generatedCertificateState({
          data: null,
        }),
      }),
      pod: factory.podState({
        loaded: true,
      }),
    });
    newPodValues = {
      certificate: "",
      key: "",
      name: "my-favourite-kvm",
      password: "",
      pool: "0",
      power_address: "192.168.1.1",
      zone: "0",
    };
  });

  it(`shows a spinner if authenticating with a certificate and no projects exist
    for that LXD address`, async () => {
    state.pod.projects = {
      "192.168.1.1": [],
    };
    renderWithProviders(
      <AuthenticationForm
        newPodValues={newPodValues}
        setNewPodValues={vi.fn()}
        setStep={vi.fn()}
      />,
      { initialEntries: ["/kvm/add"], state }
    );
    // Trusting via certificate is selected by default, so spinner should show
    // after submitting the form.
    expect(
      screen.queryByTestId("trust-confirmation-spinner")
    ).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Check authentication" })
    );
    expect(
      screen.getByTestId("trust-confirmation-spinner")
    ).toBeInTheDocument();
  });

  it("dispatches an action to poll LXD server if authenticating via certificate", async () => {
    const setNewPodValues = vi.fn();
    const generatedCert = factory.generatedCertificate({
      CN: "my-favourite-kvm@host",
    });
    state.general.generatedCertificate.data = generatedCert;

    const { store } = renderWithProviders(
      <AuthenticationForm
        newPodValues={newPodValues}
        setNewPodValues={setNewPodValues}
        setStep={vi.fn()}
      />,
      { initialEntries: ["/kvm/add"], state }
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Check authentication" })
    );

    const expectedAction = podActions.pollLxdServer({
      certificate: generatedCert.certificate,
      key: generatedCert.private_key,
      power_address: "192.168.1.1",
    });
    const actualAction = store
      .getActions()
      .find((action) => action.type === "pod/pollLxdServer");
    expect(setNewPodValues).toHaveBeenCalledWith({
      ...newPodValues,
      certificate: generatedCert.certificate,
      key: generatedCert.private_key,
    });
    expect(actualAction).toStrictEqual(expectedAction);
  });

  it("dispatches an action to fetch projects if using a password", async () => {
    const setNewPodValues = vi.fn();
    const generatedCert = factory.generatedCertificate({
      CN: "my-favourite-kvm@host",
    });
    state.general.generatedCertificate.data = generatedCert;

    const { store } = renderWithProviders(
      <AuthenticationForm
        newPodValues={newPodValues}
        setNewPodValues={setNewPodValues}
        setStep={vi.fn()}
      />,
      { initialEntries: ["/kvm/add"], state }
    );
    // Change to trusting via password and submit the form.
    await userEvent.click(
      screen.getByRole("radio", { name: "Use trust password (not secure!)" })
    );
    await userEvent.type(screen.getByLabelText("Password"), "password");
    await userEvent.click(
      screen.getByRole("button", { name: "Check authentication" })
    );

    const expectedAction = podActions.getProjects({
      certificate: generatedCert.certificate,
      key: generatedCert.private_key,
      password: "password",
      power_address: "192.168.1.1",
      type: PodType.LXD,
    });
    const actualAction = store
      .getActions()
      .find((action) => action.type === "pod/getProjects");
    expect(setNewPodValues).toHaveBeenCalledWith({
      ...newPodValues,
      password: "password",
    });
    expect(actualAction).toStrictEqual(expectedAction);
  });

  it(`reverts back to credentials step if attempt to fetch projects using a
    password results in error`, async () => {
    const setStep = vi.fn();
    state.pod.errors = "it didn't work";
    renderWithProviders(
      <AuthenticationForm
        newPodValues={newPodValues}
        setNewPodValues={vi.fn()}
        setStep={setStep}
      />,
      { initialEntries: ["/kvm/add"], state }
    );
    // Change to trusting via password and submit the form.
    await userEvent.click(
      screen.getByRole("radio", { name: "Use trust password (not secure!)" })
    );
    await userEvent.type(screen.getByLabelText("Password"), "password");
    await userEvent.click(
      screen.getByRole("button", { name: "Check authentication" })
    );

    expect(setStep).toHaveBeenCalledWith(AddLxdSteps.CREDENTIALS);
  });

  it("displays errors when it failed to trust the cert", async () => {
    const setStep = vi.fn();
    state.pod.errors = "it didn't work";
    renderWithProviders(
      <AuthenticationForm
        newPodValues={newPodValues}
        setNewPodValues={vi.fn()}
        setStep={setStep}
      />,
      { initialEntries: ["/kvm/add"], state }
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Check authentication" })
    );
    expect(screen.getByText("it didn't work")).toBeInTheDocument();
    // It should not have reverted to the previous screen.
    expect(setStep).not.toHaveBeenCalledWith(AddLxdSteps.CREDENTIALS);
  });

  it("does not display errors when attempting to trust the cert", async () => {
    const setStep = vi.fn();
    state.pod.errors = "Certificate is not trusted and no password was given";
    renderWithProviders(
      <AuthenticationForm
        newPodValues={newPodValues}
        setNewPodValues={vi.fn()}
        setStep={setStep}
      />,
      { initialEntries: ["/kvm/add"], state }
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Check authentication" })
    );
    expect(
      screen.queryByText("Certificate is not trusted and no password was given")
    ).not.toBeInTheDocument();
    // It should not have reverted to the previous screen.
    expect(setStep).not.toHaveBeenCalledWith(AddLxdSteps.CREDENTIALS);
  });

  it("moves to the project select step if projects exist for given LXD address", () => {
    const setStep = vi.fn();
    state.pod.projects = {
      "192.168.1.1": [factory.podProject()],
    };
    renderWithProviders(
      <AuthenticationForm
        newPodValues={newPodValues}
        setNewPodValues={vi.fn()}
        setStep={setStep}
      />,
      { initialEntries: ["/kvm/add"], state }
    );

    expect(setStep).toHaveBeenCalledWith(AddLxdSteps.SELECT_PROJECT);
  });

  it("clears certificate and stops polling LXD server on unmount", () => {
    const {
      result: { unmount },
      store,
    } = renderWithProviders(
      <AuthenticationForm
        newPodValues={newPodValues}
        setNewPodValues={vi.fn()}
        setStep={vi.fn()}
      />,
      { initialEntries: ["/kvm/add"], state }
    );

    unmount();

    const expectedActions = [
      generalActions.clearGeneratedCertificate(),
      podActions.pollLxdServerStop(),
    ];
    const actualActions = store.getActions();
    expect(
      actualActions.every((actualAction) =>
        expectedActions.some(
          (expectedAction) => expectedAction.type === actualAction.type
        )
      )
    );
  });
});
