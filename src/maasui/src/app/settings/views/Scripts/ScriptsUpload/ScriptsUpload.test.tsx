import type { FileWithPath } from "react-dropzone";
import type { Dispatch } from "redux";

import ScriptsUpload, { Labels as ScriptsUploadLabels } from "./ScriptsUpload";
import type { ReadScriptResponse } from "./readScript";
import * as readScript from "./readScript";

import type { RootState } from "@/app/store/root/types";
import { ScriptType } from "@/app/store/script/types";
import * as factory from "@/testing/factories";
import {
  fireEvent,
  mockSidePanel,
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/testing/utils";

const { mockClose } = await mockSidePanel();

vi.mock("./readScript", async () => {
  const actual: typeof readScript = await vi.importActual("./readScript");
  return {
    ...actual,
    readScript: vi.fn(),
  };
});

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

describe("ScriptsUpload", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      script: factory.scriptState({
        loaded: true,
      }),
    });
  });

  it("accepts files of any mimetype", async () => {
    const files = [createFile("foo.sh", 2000, "")];

    renderWithProviders(<ScriptsUpload type="testing" />, {
      state,
    });

    const upload = screen.getByLabelText(ScriptsUploadLabels.FileUploadArea);
    await userEvent.upload(upload, files);

    await waitFor(() => {
      expect(
        screen.getByText("./foo.sh (2000 bytes) ready for upload.")
      ).toBeInTheDocument();
    });
  });

  it("displays an error if a file larger than 2MB is uploaded", async () => {
    const files = [createFile("foo.sh", 3000000, "text/script")];

    const { store } = renderWithProviders(<ScriptsUpload type="testing" />, {
      state,
    });

    const upload = screen.getByLabelText(ScriptsUploadLabels.FileUploadArea);
    await userEvent.upload(upload, files);

    expect(store.getActions()[0].payload.message).toEqual(
      "foo.sh: File is larger than 2000000 bytes"
    );
  });

  it("displays a single error if multiple files are uploaded", async () => {
    const files = [
      createFile("foo.sh", 1000, "text/script"),
      createFile("bar.sh", 1000, "text/script"),
    ];

    const { store } = renderWithProviders(<ScriptsUpload type="testing" />, {
      state,
    });

    const upload = screen.getByLabelText(ScriptsUploadLabels.FileUploadArea);
    // necessary to use a fireEvent instead of userEvent, since userEvent doesn't support "drag n drop" multiple file upload
    fireEvent.drop(upload, { target: { files } });
    await waitFor(() => {
      expect(store.getActions()[0].payload.message).toEqual(
        "Only a single file may be uploaded."
      );
    });
    expect(store.getActions().length).toBe(1);
  });

  it("dispatches uploadScript without a name if script has metadata", async () => {
    const contents = "# --- Start MAAS 1.0 script metadata ---";
    vi.spyOn(readScript, "readScript").mockImplementation(
      (
        _name: FileWithPath,
        _script: Dispatch,
        callback: (script: ReadScriptResponse | null) => void
      ) => {
        callback({
          name: "foo",
          script: contents,
          hasMetadata: true,
        });
      }
    );
    const files = [createFile("foo.sh", 1000, "text/script", contents)];

    const { store } = renderWithProviders(<ScriptsUpload type="testing" />, {
      state,
    });

    const upload = screen.getByLabelText(ScriptsUploadLabels.FileUploadArea);
    await userEvent.upload(upload, files);

    await userEvent.click(
      screen.getByRole("button", { name: ScriptsUploadLabels.SubmitButton })
    );

    expect(store.getActions()).toEqual([
      { type: "script/cleanup" },
      {
        payload: { contents, type: ScriptType.TESTING },
        type: "script/upload",
      },
    ]);
  });

  it("dispatches uploadScript with a name if script has no metadata", async () => {
    const contents = "#!/bin/bash\necho 'foo';\n";
    vi.spyOn(readScript, "readScript").mockImplementation(
      (
        _name: FileWithPath,
        _script: Dispatch,
        callback: (script: ReadScriptResponse | null) => void
      ) => {
        callback({
          name: "foo",
          script: contents,
          hasMetadata: false,
        });
      }
    );
    const files = [createFile("foo.sh", 1000, "text/script", contents)];

    const { store } = renderWithProviders(<ScriptsUpload type="testing" />, {
      state,
    });

    const upload = screen.getByLabelText(ScriptsUploadLabels.FileUploadArea);
    await userEvent.upload(upload, files);

    await userEvent.click(
      screen.getByRole("button", { name: ScriptsUploadLabels.SubmitButton })
    );

    expect(store.getActions()).toEqual([
      { type: "script/cleanup", payload: undefined },
      {
        payload: { contents, type: ScriptType.TESTING, name: "foo.sh" },
        type: "script/upload",
      },
    ]);
  });

  it("can cancel and return to the commissioning list", async () => {
    renderWithProviders(<ScriptsUpload type="commissioning" />, {
      state,
    });
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("can cancel and return to the testing list", async () => {
    renderWithProviders(<ScriptsUpload type="testing" />, {
      state,
    });
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("can cancel and return to the deployment list", async () => {
    renderWithProviders(<ScriptsUpload type="deployment" />, {
      state,
    });
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });
});
