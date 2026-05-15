import { Formik } from "formik";

import { DeviceType } from "../types";

import DiscoveryAddFormFields, {
  Labels as DiscoveryAddFormFieldsLabels,
} from "./DiscoveryAddFormFields";

import type { DiscoveryResponse } from "@/app/apiclient";
import { DeviceMeta } from "@/app/store/device/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  within,
  renderWithProviders,
} from "@/testing/utils";

describe("DiscoveryAddFormFields", () => {
  let state: RootState;
  let discovery: DiscoveryResponse;

  beforeEach(() => {
    discovery = factory.discovery();
    state = factory.rootState({});
  });

  it("shows fields for a device", () => {
    renderWithProviders(
      <Formik initialValues={{ type: DeviceType.DEVICE }} onSubmit={vi.fn()}>
        <DiscoveryAddFormFields
          discovery={discovery}
          setDevice={vi.fn()}
          setDeviceType={vi.fn()}
        />
      </Formik>,
      {}
    );
    expect(
      screen.getByRole("combobox", {
        name: DiscoveryAddFormFieldsLabels.Domain,
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: DiscoveryAddFormFieldsLabels.Parent,
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("textbox", {
        name: DiscoveryAddFormFieldsLabels.Hostname,
      })
    ).toBeInTheDocument();

    expect(
      screen.queryByRole("textbox", {
        name: DiscoveryAddFormFieldsLabels.InterfaceName,
      })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", {
        name: DiscoveryAddFormFieldsLabels.DeviceName,
      })
    ).not.toBeInTheDocument();
  });

  it("shows fields for an interface", () => {
    renderWithProviders(
      <Formik initialValues={{ type: DeviceType.INTERFACE }} onSubmit={vi.fn()}>
        <DiscoveryAddFormFields
          discovery={discovery}
          setDevice={vi.fn()}
          setDeviceType={vi.fn()}
        />
      </Formik>,
      {}
    );
    expect(
      screen.queryByRole("combobox", {
        name: DiscoveryAddFormFieldsLabels.Domain,
      })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", {
        name: DiscoveryAddFormFieldsLabels.Parent,
      })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("textbox", {
        name: DiscoveryAddFormFieldsLabels.Hostname,
      })
    ).not.toBeInTheDocument();

    expect(
      screen.getByRole("textbox", {
        name: DiscoveryAddFormFieldsLabels.InterfaceName,
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", {
        name: DiscoveryAddFormFieldsLabels.DeviceName,
      })
    ).toBeInTheDocument();
  });

  it("includes static ip if there is a subnet", () => {
    discovery.subnet_id = 0;
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <DiscoveryAddFormFields
          discovery={discovery}
          setDevice={vi.fn()}
          setDeviceType={vi.fn()}
        />
      </Formik>,
      {}
    );

    const ipAssignment = screen.getByRole("combobox", {
      name: "IP assignment",
    });

    expect(
      within(ipAssignment).getByRole("option", {
        name: "Static (Client configured)",
      })
    ).toBeInTheDocument();
  });

  it("does not includes static ip if there is no subnet", () => {
    discovery.subnet_id = undefined;
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <DiscoveryAddFormFields
          discovery={discovery}
          setDevice={vi.fn()}
          setDeviceType={vi.fn()}
        />
      </Formik>,
      {}
    );

    const ipAssignment = screen.getByRole("combobox", {
      name: "IP assignment",
    });

    expect(
      within(ipAssignment).queryByRole("option", {
        name: "Static",
      })
    ).not.toBeInTheDocument();
  });

  it("calls the callback with the selected device type", async () => {
    const setDeviceType = vi.fn();
    const setDevice = vi.fn();
    state.device = factory.deviceState({
      items: [
        factory.device({ [DeviceMeta.PK]: "abc123" }),
        factory.device({ [DeviceMeta.PK]: "def456" }),
      ],
    });
    renderWithProviders(
      <Formik initialValues={{ type: DeviceType.INTERFACE }} onSubmit={vi.fn()}>
        <DiscoveryAddFormFields
          discovery={discovery}
          setDevice={setDevice}
          setDeviceType={setDeviceType}
        />
      </Formik>,
      { state }
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: DiscoveryAddFormFieldsLabels.Type }),
      DeviceType.INTERFACE
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", {
        name: DiscoveryAddFormFieldsLabels.DeviceName,
      }),
      "abc123"
    );
    expect(setDeviceType).toHaveBeenCalledWith(DeviceType.INTERFACE);
    // The device should get cleared.
    expect(setDevice).toHaveBeenCalledWith(null);
  });

  it("calls the callback with the device id when selecting a device", async () => {
    const setDevice = vi.fn();
    state.device = factory.deviceState({
      items: [
        factory.device({ [DeviceMeta.PK]: "abc123" }),
        factory.device({ [DeviceMeta.PK]: "def456" }),
      ],
    });
    renderWithProviders(
      <Formik initialValues={{ type: DeviceType.INTERFACE }} onSubmit={vi.fn()}>
        <DiscoveryAddFormFields
          discovery={discovery}
          setDevice={setDevice}
          setDeviceType={vi.fn()}
        />
      </Formik>,
      { state }
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", {
        name: DiscoveryAddFormFieldsLabels.DeviceName,
      }),
      "abc123"
    );
    expect(setDevice).toHaveBeenCalledWith("abc123");
  });
});
