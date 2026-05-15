import { Formik } from "formik";
import type { Mock } from "vitest";

import UploadTextArea from "./UploadTextArea";

import { render, screen, userEvent, waitFor } from "@/testing/utils";

class MockFileReader {
  result: string;
  constructor() {
    this.result = "test file content";
  }
  onabort = () => undefined;
  onerror = () => undefined;
  onloadend = () => undefined;
  readAsText() {
    this.onloadend();
  }
}

const createFile = (
  name: string,
  size: number,
  type: string,
  contents = ""
) => {
  const file = new File([contents], name, { type });
  Reflect.defineProperty(file, "size", {
    get() {
      return size;
    },
  });
  return file;
};

const getFileUploadInput = (container: HTMLElement) => {
  return container.querySelector("input[type='file']") as HTMLElement;
};

describe("UploadTextArea", () => {
  beforeEach(async () => {
    const mockedFileReader = vi.spyOn(window, "FileReader");
    (mockedFileReader as Mock).mockImplementation(() => new MockFileReader());
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("accepts files of any mimetype", async () => {
    const files = [createFile("foo.sh", 2000, "")];
    const { container } = render(
      <Formik initialValues={{ key: "" }} onSubmit={vi.fn()}>
        <UploadTextArea label="Upload" name="key" />
      </Formik>
    );
    await userEvent.upload(getFileUploadInput(container), files);
    await waitFor(() => {
      expect(screen.queryByRole("alert")).toBeNull();
    });
  });

  it("displays an error if a file is larger than max size", async () => {
    const files = [createFile("foo.sh", 2000000, "")];
    const { container } = render(
      <Formik initialValues={{ key: "" }} onSubmit={vi.fn()}>
        <UploadTextArea label="Upload" maxSize={1000000} name="key" />
      </Formik>
    );
    await userEvent.upload(getFileUploadInput(container), files);
    await waitFor(() => {
      expect(
        screen.getByText(/File cannot be larger than 1MB./i)
      ).toBeInTheDocument();
    });
  });

  it("can populate the textarea from the file", async () => {
    const files = [createFile("foo.sh", 2000, "text/script")];
    const { container } = render(
      <Formik initialValues={{ key: "" }} onSubmit={vi.fn()}>
        <UploadTextArea label="Upload" name="key" />
      </Formik>
    );
    await userEvent.upload(getFileUploadInput(container), files);
    await waitFor(() => {
      expect(screen.getByRole("textbox")).toHaveValue("test file content");
    });
  });

  it("clears errors on textarea change", async () => {
    const files = [createFile("foo.sh", 2000000, "text/script")];
    const { container } = render(
      <Formik initialValues={{ key: "" }} onSubmit={vi.fn()}>
        <UploadTextArea label="Upload" maxSize={1000000} name="key" />
      </Formik>
    );
    // Create a max size error
    await userEvent.upload(getFileUploadInput(container), files);
    await waitFor(() => {
      expect(
        screen.getByText(/File cannot be larger than 1MB./i)
      ).toBeInTheDocument();
    });

    // Clear error by changing textarea
    const textarea = screen.getByRole("textbox");
    await userEvent.type(textarea, "new-value");
    await waitFor(() => {
      expect(screen.queryByRole("alert")).toBeNull();
    });
  });
});
