import { expect, it } from "vitest";

import { MAAS_IO_DEFAULT_KEYRING_FILE_PATHS } from "@/app/images/constants";
import AddSource from "@/app/settings/views/Images/Sources/components/AddSource/AddSource";
import { Labels } from "@/app/settings/views/Images/Sources/constants";
import * as factory from "@/testing/factories";
import { imageSourceResolvers } from "@/testing/resolvers/imageSources";
import {
  userEvent,
  renderWithProviders,
  screen,
  waitForLoading,
  waitFor,
  setupMockServer,
  mockSidePanel,
} from "@/testing/utils";

const mockServer = setupMockServer(
  imageSourceResolvers.fetchImageSource.handler(),
  imageSourceResolvers.createImageSource.handler()
);
const { mockClose } = await mockSidePanel();

describe("AddSource", () => {
  it("calls closeForm on cancel click", async () => {
    renderWithProviders(<AddSource />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("switches between keyring filename and keyring data fields when selecting different options", async () => {
    renderWithProviders(<AddSource />);

    expect(
      screen.getByRole("textbox", { name: Labels.KeyringFilename })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("textbox", { name: Labels.KeyringData })
    ).not.toBeInTheDocument();

    // Switch to keyring_data
    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "keyring_data");

    expect(
      screen.queryByRole("textbox", { name: Labels.KeyringFilename })
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("textbox", { name: Labels.KeyringData })
    ).toBeInTheDocument();
  });

  it("clears the other field when switching between keyring types", async () => {
    renderWithProviders(<AddSource />);

    // The default keyring filename is the snap path when no install type is set
    expect(
      screen.getByRole("textbox", { name: Labels.KeyringFilename })
    ).toHaveValue(MAAS_IO_DEFAULT_KEYRING_FILE_PATHS.snap);

    // Switch to keyring_data
    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "keyring_data");

    // keyring_data field should now be visible and empty
    expect(
      screen.getByRole("textbox", { name: Labels.KeyringData })
    ).toHaveValue("");

    // Switch back to keyring_filename
    await userEvent.selectOptions(select, "keyring_filename");

    // URL should still have its (empty) initial value
    expect(screen.getByRole("textbox", { name: Labels.Url })).toHaveValue("");
  });

  it("pre-populates custom source with correct default keyring based on install type", async () => {
    const state = factory.rootState({
      general: factory.generalState({
        installType: factory.installTypeState({ data: "deb" }),
      }),
    });
    // Test with deb install type
    const { rerender } = renderWithProviders(<AddSource />, {
      state,
    });

    // Verify deb default keyring is shown
    expect(
      screen.getByRole("textbox", { name: Labels.KeyringFilename })
    ).toHaveValue(MAAS_IO_DEFAULT_KEYRING_FILE_PATHS.deb);

    // Test with snap install type
    state.general.installType = factory.installTypeState({ data: "snap" });
    rerender(<AddSource />, { state });

    // Verify snap default keyring is shown
    expect(
      screen.getByRole("textbox", { name: Labels.KeyringFilename })
    ).toHaveValue(MAAS_IO_DEFAULT_KEYRING_FILE_PATHS.snap);
  });

  it("does not display keyring fields when unsigned keyring type is selected", async () => {
    renderWithProviders(<AddSource />);
    await waitForLoading();

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "keyring_unsigned");

    expect(
      screen.getByRole("textbox", { name: Labels.Url })
    ).toBeInTheDocument();

    expect(
      screen.queryByPlaceholderText(
        "e.g. /usr/share/keyrings/ubuntu-cloudimage-keyring.gpg"
      )
    ).not.toBeInTheDocument();
    expect(
      screen.queryByPlaceholderText("Contents of GPG key (base64 encoded)")
    ).not.toBeInTheDocument();
  });

  it("shows error when keyring_filename is empty and keyring_type is keyring_filename", async () => {
    renderWithProviders(<AddSource />);
    await waitForLoading();

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "keyring_filename");

    // Focus and blur the keyring filename field to trigger validation
    const keyringFilenameInput = screen.getByPlaceholderText(
      "e.g. /usr/share/keyrings/ubuntu-cloudimage-keyring.gpg"
    );
    await userEvent.click(keyringFilenameInput);
    await userEvent.clear(keyringFilenameInput);
    await userEvent.tab();

    await waitFor(() => {
      expect(
        screen.getByText("Keyring filename is required")
      ).toBeInTheDocument();
    });
  });

  it("shows error when keyring_data is empty and keyring_type is keyring_data", async () => {
    renderWithProviders(<AddSource />);
    await waitForLoading();

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "keyring_data");

    // Focus and blur the keyring data field to trigger validation
    const keyringDataInput = screen.getByPlaceholderText(
      "Contents of GPG key (base64 encoded)"
    );
    await userEvent.click(keyringDataInput);
    await userEvent.tab();

    await waitFor(() => {
      expect(screen.getByText("Keyring data is required")).toBeInTheDocument();
    });
  });

  it("displays error and keeps button as Validate if fetch fails", async () => {
    mockServer.use(
      imageSourceResolvers.fetchImageSource.error({
        message: "Invalid boot source URL",
        code: 400,
      })
    );

    renderWithProviders(<AddSource />);
    await waitForLoading();

    const urlInput = screen.getByRole("textbox", { name: Labels.Url });
    await userEvent.clear(urlInput);
    await userEvent.type(urlInput, "http://invalid.example.com/");

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "keyring_unsigned");

    await userEvent.click(screen.getByRole("button", { name: "Validate" }));

    await waitFor(() => {
      expect(screen.getByText("Invalid boot source URL")).toBeInTheDocument();
    });

    // "Save" should be disabled, while "Validate" still enabled
    expect(screen.getByRole("button", { name: "Validate" })).toBeEnabled();
    expect(
      screen.queryByRole("button", { name: "Save source" })
    ).toBeDisabled();
  });

  it("calls create source on save click", async () => {
    renderWithProviders(<AddSource />);
    await waitForLoading();
    const nameInput = screen.getByRole("textbox", { name: Labels.Name });
    await userEvent.type(nameInput, "Custom Source");
    const urlInput = screen.getByRole("textbox", { name: Labels.Url });
    await userEvent.clear(urlInput);
    await userEvent.type(urlInput, "http://invalid.example.com/");

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "keyring_unsigned");

    await userEvent.click(screen.getByRole("button", { name: "Validate" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Save source" })).toBeEnabled();
    });

    await userEvent.click(screen.getByRole("button", { name: "Save source" }));
    await waitFor(() => {
      expect(imageSourceResolvers.createImageSource.resolved).toBeTruthy();
    });
  });

  it("displays error messages when create source fails", async () => {
    mockServer.use(
      imageSourceResolvers.createImageSource.error({
        code: 400,
        message: "Uh oh!",
      })
    );
    renderWithProviders(<AddSource />);
    await waitForLoading();
    const nameInput = screen.getByRole("textbox", { name: Labels.Name });
    await userEvent.type(nameInput, "Custom Source");
    const urlInput = screen.getByRole("textbox", { name: Labels.Url });
    await userEvent.clear(urlInput);
    await userEvent.type(urlInput, "http://invalid.example.com/");

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "keyring_unsigned");

    await userEvent.click(screen.getByRole("button", { name: "Validate" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Save source" })).toBeEnabled();
    });

    await userEvent.click(screen.getByRole("button", { name: "Save source" }));
    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });
});
