import UploadCustomImage from "./UploadCustomImage";

import { imageResolvers } from "@/testing/resolvers/images";
import {
  userEvent,
  screen,
  mockSidePanel,
  renderWithProviders,
  setupMockServer,
  waitForLoading,
  waitFor,
} from "@/testing/utils";

const { mockClose } = await mockSidePanel();
const mockServer = setupMockServer(imageResolvers.uploadCustomImage.handler());

// Mock File.prototype.arrayBuffer for tests
if (!File.prototype.arrayBuffer) {
  File.prototype.arrayBuffer = function () {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = () => {
        resolve(reader.result as ArrayBuffer);
      };
      reader.readAsArrayBuffer(this);
    });
  };
}

// Mock File.prototype.stream for MSW
if (!File.prototype.stream) {
  File.prototype.stream = function () {
    // Return a mock ReadableStream
    return new ReadableStream({
      start(controller) {
        controller.enqueue(new Uint8Array([]));
        controller.close();
      },
    }) as unknown as ReadableStream;
  };
}

describe("UploadCustomImage", () => {
  it("calls closeForm on cancel click", async () => {
    renderWithProviders(<UploadCustomImage />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls upload images on save click", async () => {
    const { result } = renderWithProviders(<UploadCustomImage />);
    await waitForLoading();

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /operating system/i }),
      "Ubuntu Core"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /release title/i }),
      "24.04 LTS"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /release codename/i }),
      "noble"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /architecture/i }),
      "amd64"
    );
    const file = new File(["dummy content"], "test-image.tgz");
    const fileInput = result.container.querySelector(
      "input[type='file']"
    ) as HTMLInputElement;
    await userEvent.upload(fileInput, file);

    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    await waitFor(() => {
      expect(imageResolvers.uploadCustomImage.resolved).toBeTruthy();
    });
  });

  it("displays error messages when image upload fails", async () => {
    mockServer.use(
      imageResolvers.uploadCustomImage.error({ code: 400, message: "Uh oh!" })
    );
    const { result } = renderWithProviders(<UploadCustomImage />);
    await waitForLoading();

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /operating system/i }),
      "Ubuntu Core"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /release title/i }),
      "24.04 LTS"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /release codename/i }),
      "noble"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /architecture/i }),
      "amd64"
    );
    const file = new File(["dummy content"], "test-image.tgz");
    const fileInput = result.container.querySelector(
      "input[type='file']"
    ) as HTMLInputElement;
    await userEvent.upload(fileInput, file);

    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });

  it("conditionally renders/hides base image fields when OS is Custom", async () => {
    renderWithProviders(<UploadCustomImage />);
    await waitForLoading();

    // Base image fields should not be visible initially
    expect(
      screen.queryByRole("combobox", { name: /base image operating system/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("textbox", { name: /base image release codename/i })
    ).not.toBeInTheDocument();

    // Select Custom OS
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /^operating system/i }),
      "Custom"
    );

    // Base image fields should now be visible
    await waitFor(() => {
      expect(
        screen.getByRole("combobox", { name: /base image operating system/i })
      ).toBeInTheDocument();
    });
    expect(
      screen.getByRole("textbox", { name: /base image release codename/i })
    ).toBeInTheDocument();

    // Select a different OS
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /^operating system/i }),
      "Ubuntu Core"
    );

    // Base image fields should be hidden again
    await waitFor(() => {
      expect(
        screen.queryByRole("combobox", { name: /base image operating system/i })
      ).not.toBeInTheDocument();
    });
    expect(
      screen.queryByRole("textbox", { name: /base image release codename/i })
    ).not.toBeInTheDocument();
  });

  it("should show error when submitting without file", async () => {
    renderWithProviders(<UploadCustomImage />);
    await waitForLoading();

    // Fill in all fields except file
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /operating system/i }),
      "Ubuntu Core"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /release title/i }),
      "24.04 LTS"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /release codename/i }),
      "noble"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /architecture/i }),
      "amd64"
    );

    // Submit button should be disabled without file
    const submitButton = screen.getByRole("button", { name: "Upload" });
    expect(submitButton).toBeDisabled();
  });

  it("should show errors for all required fields when empty", async () => {
    renderWithProviders(<UploadCustomImage />);
    await waitForLoading();

    // Touch all fields without filling them
    const osSelect = screen.getByRole("combobox", {
      name: /operating system/i,
    });
    const titleInput = screen.getByRole("textbox", { name: /release title/i });
    const releaseInput = screen.getByRole("textbox", {
      name: /release codename/i,
    });
    const archSelect = screen.getByRole("combobox", { name: /architecture/i });

    // Focus and blur each field to trigger validation
    await userEvent.click(osSelect);
    await userEvent.tab();
    await userEvent.click(titleInput);
    await userEvent.tab();
    await userEvent.click(releaseInput);
    await userEvent.tab();
    await userEvent.click(archSelect);
    await userEvent.tab();

    // Check for validation errors
    await waitFor(() => {
      expect(screen.getByText(/OS is required/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Release title is required/i)).toBeInTheDocument();
    expect(screen.getByText(/Release is required/i)).toBeInTheDocument();
    expect(screen.getByText(/Architecture is required/i)).toBeInTheDocument();
  });

  it("should clear file error when valid file is uploaded", async () => {
    const { result } = renderWithProviders(<UploadCustomImage />);
    await waitForLoading();

    // Fill in other required fields
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /operating system/i }),
      "Ubuntu Core"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /release title/i }),
      "24.04 LTS"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /release codename/i }),
      "noble"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /architecture/i }),
      "amd64"
    );

    // Submit button should be disabled without file
    const submitButton = screen.getByRole("button", { name: "Upload" });
    expect(submitButton).toBeDisabled();

    // Upload a valid file
    const file = new File(["dummy content"], "test-image.tgz");
    const fileInput = result.container.querySelector(
      "input[type='file']"
    ) as HTMLInputElement;
    await userEvent.upload(fileInput, file);

    // Submit button should now be enabled
    await waitFor(() => {
      expect(submitButton).not.toBeDisabled();
    });
  });

  it("should validate on change", async () => {
    renderWithProviders(<UploadCustomImage />);
    await waitForLoading();

    const releaseInput = screen.getByRole("textbox", {
      name: /release title/i,
    });

    // Type and then blur to trigger validation
    await userEvent.type(releaseInput, "Test");
    await userEvent.tab(); // Blur the field

    // Now clear the field - this should show validation error
    await userEvent.clear(releaseInput);

    // Should show validation error after clearing
    await waitFor(() => {
      expect(
        screen.getByText(/Release title is required/i)
      ).toBeInTheDocument();
    });

    // Fill the field again
    await userEvent.type(releaseInput, "Valid Title");

    // Error should be cleared
    await waitFor(() => {
      expect(
        screen.queryByText(/Release title is required/i)
      ).not.toBeInTheDocument();
    });
  });
});
