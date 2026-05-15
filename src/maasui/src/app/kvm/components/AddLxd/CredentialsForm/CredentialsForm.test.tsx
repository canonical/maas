import { AddLxdSteps } from "../AddLxd";
import type { NewPodValues } from "../types";

import CredentialsForm from "./CredentialsForm";

import { generalActions } from "@/app/store/general";
import { podActions } from "@/app/store/pod";
import { PodType } from "@/app/store/pod/constants";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { poolsResolvers } from "@/testing/resolvers/pools";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  screen,
  userEvent,
  renderWithProviders,
  setupMockServer,
} from "@/testing/utils";

setupMockServer(
  poolsResolvers.listPools.handler(),
  zoneResolvers.listZones.handler()
);

describe("CredentialsForm", () => {
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
      pool: "1",
      power_address: "192.168.1.1",
      zone: "2",
    };
  });

  it("dispatches an action to generate certificate if not providing certificate and key", async () => {
    const setNewPodValues = vi.fn();

    const { store } = renderWithProviders(
      <CredentialsForm
        newPodValues={newPodValues}
        setNewPodValues={setNewPodValues}
        setStep={vi.fn()}
        setSubmissionErrors={vi.fn()}
      />,
      { initialEntries: ["/kvm/add"], state }
    );

    // Submit form
    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(setNewPodValues).toHaveBeenCalledWith({
      certificate: "",
      key: "",
      name: "my-favourite-kvm",
      password: "",
      pool: "1",
      power_address: "192.168.1.1",
      zone: "2",
    });

    const expectedAction = generalActions.generateCertificate({
      object_name: "my-favourite-kvm",
    });
    const actualActions = store.getActions();
    expect(
      actualActions.find(
        (action) => action.type === "general/generateCertificate"
      )
    ).toStrictEqual(expectedAction);
    expect(
      actualActions.find((action) => action.type === "pod/getProjects")
    ).toBeUndefined();
  });

  it("dispatches an action to fetch projects if providing certificate and key", async () => {
    const setNewPodValues = vi.fn();

    newPodValues.certificate = "certificate";
    newPodValues.key = "key";
    newPodValues.zone = "4";
    newPodValues.pool = "3";
    const { store } = renderWithProviders(
      <CredentialsForm
        newPodValues={newPodValues}
        setNewPodValues={setNewPodValues}
        setStep={vi.fn()}
        setSubmissionErrors={vi.fn()}
      />,
      { initialEntries: ["/kvm/add"], state }
    );
    // Change radio to provide certificate instead of generating one.
    await userEvent.click(
      screen.getByRole("radio", { name: "Provide certificate and private key" })
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: "Upload certificate" }),
      "certificate"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Upload private key" }),
      "key"
    );

    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(setNewPodValues).toHaveBeenCalledWith({
      certificate: "certificate",
      key: "key",
      name: "my-favourite-kvm",
      password: "",
      pool: "3",
      power_address: "192.168.1.1",
      zone: "4",
    });
    const expectedAction = podActions.getProjects({
      certificate: "certificate",
      key: "key",
      power_address: "192.168.1.1",
      type: PodType.LXD,
    });
    const actualActions = store.getActions();
    expect(
      actualActions.find((action) => action.type === "pod/getProjects")
    ).toStrictEqual(expectedAction);
    expect(
      actualActions.find(
        (action) => action.type === "general/generateCertificate"
      )
    ).toBeUndefined();
  });

  it("moves to the authentication step if certificate successfully generated", () => {
    const setStep = vi.fn();
    state.general.generatedCertificate.data = factory.generatedCertificate({
      CN: "my-favourite-kvm@host",
    });

    renderWithProviders(
      <CredentialsForm
        newPodValues={{
          certificate: "",
          key: "",
          name: "my-favourite-kvm",
          password: "",
          pool: "0",
          power_address: "192.168.1.1",
          zone: "0",
        }}
        setNewPodValues={vi.fn()}
        setStep={setStep}
        setSubmissionErrors={vi.fn()}
      />,
      { initialEntries: ["/kvm/add"], state }
    );

    expect(setStep).toHaveBeenCalledWith(AddLxdSteps.AUTHENTICATION);
  });

  it(`does not move to the authentication step if certificate successfully
      generated but errors are present`, () => {
    const setStep = vi.fn();
    state.general.generatedCertificate.data = factory.generatedCertificate({
      CN: "my-favourite-kvm@host",
    });
    state.pod.errors = "Failed to connect to LXD.";

    renderWithProviders(
      <CredentialsForm
        newPodValues={{
          certificate: "",
          key: "",
          name: "my-favourite-kvm",
          password: "",
          pool: "0",
          power_address: "192.168.1.1",
          zone: "0",
        }}
        setNewPodValues={vi.fn()}
        setStep={setStep}
        setSubmissionErrors={vi.fn()}
      />,
      { initialEntries: ["/kvm/add"], state }
    );

    expect(setStep).not.toHaveBeenCalled();
  });

  it("moves to the project select step if projects exist for given LXD address", () => {
    const setStep = vi.fn();
    state.pod.projects = {
      "192.168.1.1": [factory.podProject()],
    };

    renderWithProviders(
      <CredentialsForm
        newPodValues={{
          certificate: "certificate",
          key: "key",
          name: "my-favourite-kvm",
          password: "",
          pool: "0",
          power_address: "192.168.1.1",
          zone: "0",
        }}
        setNewPodValues={vi.fn()}
        setStep={setStep}
        setSubmissionErrors={vi.fn()}
      />,
      { initialEntries: ["/kvm/add"], state }
    );

    expect(setStep).toHaveBeenCalledWith(AddLxdSteps.SELECT_PROJECT);
  });

  it(`does not move to the project select step if projects exist for given LXD
      address but pod errors are present`, () => {
    const setStep = vi.fn();
    state.pod.projects = {
      "192.168.1.1": [factory.podProject()],
    };
    state.pod.errors = "Failed to fetch projects.";

    renderWithProviders(
      <CredentialsForm
        newPodValues={{
          certificate: "certificate",
          key: "key",
          name: "my-favourite-kvm",
          password: "",
          pool: "0",
          power_address: "192.168.1.1",
          zone: "0",
        }}
        setNewPodValues={vi.fn()}
        setStep={setStep}
        setSubmissionErrors={vi.fn()}
      />,
      { initialEntries: ["/kvm/add"], state }
    );

    expect(setStep).not.toHaveBeenCalled();
    expect(screen.getByTestId("notification-title")).toHaveTextContent(
      "Error:"
    );
    expect(screen.getByText("Failed to fetch projects.")).toBeInTheDocument();
  });

  it("displays errors if generating a cert failed", () => {
    const setStep = vi.fn();
    state.pod.projects = {
      "192.168.1.1": [factory.podProject()],
    };
    state.general = factory.generalState({
      generatedCertificate: factory.generatedCertificateState({
        errors: "name too long",
      }),
    });

    renderWithProviders(
      <CredentialsForm
        newPodValues={{
          certificate: "certificate",
          key: "key",
          name: "my-favourite-kvm",
          password: "",
          pool: "0",
          power_address: "192.168.1.1",
          zone: "0",
        }}
        setNewPodValues={vi.fn()}
        setStep={setStep}
        setSubmissionErrors={vi.fn()}
      />,
      { initialEntries: ["/kvm/add"], state }
    );
    expect(setStep).not.toHaveBeenCalled();
    expect(screen.getByTestId("notification-title")).toHaveTextContent(
      "Error:"
    );
    expect(screen.getByText("name too long")).toBeInTheDocument();
  });

  it("clears the submission errors when unmounting", () => {
    const setSubmissionErrors = vi.fn();
    state.pod.projects = {
      "192.168.1.1": [factory.podProject()],
    };
    state.pod.errors = "Failed to fetch projects.";

    const {
      result: { unmount },
      store,
    } = renderWithProviders(
      <CredentialsForm
        newPodValues={{
          certificate: "certificate",
          key: "key",
          name: "my-favourite-kvm",
          password: "",
          pool: "0",
          power_address: "192.168.1.1",
          zone: "0",
        }}
        setNewPodValues={vi.fn()}
        setStep={vi.fn()}
        setSubmissionErrors={setSubmissionErrors}
      />,
      { initialEntries: ["/kvm/add"], state }
    );
    unmount();
    expect(
      store
        .getActions()
        .some((action) => action.type === podActions.cleanup().type)
    ).toBe(true);
    expect(
      store
        .getActions()
        .some(
          (action) =>
            action.type ===
            generalActions.cleanupGeneratedCertificateErrors().type
        )
    ).toBe(true);
    expect(setSubmissionErrors).toHaveBeenCalled();
  });
});
