import { expect, it } from "vitest";

import EditSource from "@/app/settings/views/Images/Sources/components/EditSource/EditSource";
import { Labels } from "@/app/settings/views/Images/Sources/constants";
import { imageSourceFactory } from "@/testing/factories";
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
  imageSourceResolvers.getImageSource.handler(
    imageSourceFactory.build({
      id: 1,
      name: "Custom",
      url: "http://custom.image.source/stable/",
      keyring_filename: "/custom/keyring/file.gpg",
      keyring_data: "aabbccdd",
      priority: 0,
      skip_keyring_verification: false,
    })
  ),
  imageSourceResolvers.updateImageSource.handler()
);
const { mockClose } = await mockSidePanel();

describe("EditSource", () => {
  it("calls closeForm on cancel click", async () => {
    renderWithProviders(<EditSource id={1} isDefault={false} />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("correctly renders edit fields for custom and default sources", async () => {
    const { rerender } = renderWithProviders(
      <EditSource id={1} isDefault={false} />
    );
    await waitForLoading();

    expect(
      screen.getByRole("textbox", { name: Labels.Url })
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: Labels.Url })).toHaveValue(
      "http://custom.image.source/stable/"
    );
    expect(
      screen.getByRole("textbox", { name: Labels.KeyringFilename })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("textbox", { name: Labels.KeyringFilename })
    ).toHaveValue("/custom/keyring/file.gpg");
    expect(
      screen.getByRole("spinbutton", { name: Labels.Priority })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("spinbutton", { name: Labels.Priority })
    ).toHaveValue(0);

    rerender(<EditSource id={1} isDefault={true} />);
    await waitForLoading();

    expect(
      screen.queryByRole("textbox", { name: Labels.Url })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("textbox", { name: Labels.KeyringFilename })
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("spinbutton", { name: Labels.Priority })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("spinbutton", { name: Labels.Priority })
    ).toHaveValue(0);
  });

  it("switches between keyring filename and keyring data fields when selecting different options", async () => {
    renderWithProviders(<EditSource id={1} isDefault={false} />);
    await waitForLoading();
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
    renderWithProviders(<EditSource id={1} isDefault={false} />);
    await waitForLoading();
    // The default keyring filename is the editing source filename
    expect(
      screen.getByRole("textbox", { name: Labels.KeyringFilename })
    ).toHaveValue("/custom/keyring/file.gpg");

    // Switch to keyring_data
    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "keyring_data");

    // keyring_data field should now be visible and empty
    expect(
      screen.getByRole("textbox", { name: Labels.KeyringData })
    ).toHaveValue("aabbccdd");

    // Switch back to keyring_filename
    await userEvent.selectOptions(select, "keyring_filename");

    // URL should still have its (empty) initial value
    expect(screen.getByRole("textbox", { name: Labels.Url })).toHaveValue(
      "http://custom.image.source/stable/"
    );
  });

  it("does not display keyring fields when unsigned keyring type is selected", async () => {
    renderWithProviders(<EditSource id={1} isDefault={false} />);
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
    renderWithProviders(<EditSource id={1} isDefault={false} />);
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
    renderWithProviders(<EditSource id={1} isDefault={false} />);
    await waitForLoading();

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "keyring_data");

    // Focus and blur the keyring data field to trigger validation
    const keyringDataInput = screen.getByPlaceholderText(
      "Contents of GPG key (base64 encoded)"
    );
    await userEvent.click(keyringDataInput);
    await userEvent.clear(keyringDataInput);
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

    renderWithProviders(<EditSource id={1} isDefault={false} />);
    await waitForLoading();

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

  it("calls update source on save click", async () => {
    renderWithProviders(<EditSource id={1} isDefault={false} />);
    await waitForLoading();

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "keyring_unsigned");

    await userEvent.click(screen.getByRole("button", { name: "Validate" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Save source" })).toBeEnabled();
    });

    await userEvent.click(screen.getByRole("button", { name: "Save source" }));
    await waitFor(() => {
      expect(imageSourceResolvers.updateImageSource.resolved).toBeTruthy();
    });
  });

  it("displays error messages when update source fails", async () => {
    mockServer.use(
      imageSourceResolvers.updateImageSource.error({
        code: 400,
        message: "Uh oh!",
      })
    );
    renderWithProviders(<EditSource id={1} isDefault={false} />);
    await waitForLoading();

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
