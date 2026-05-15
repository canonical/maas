import CopyButton from "./CopyButton";

import { userEvent, screen, renderWithProviders } from "@/testing/utils";

describe("CopyButton", () => {
  let execCommand: (
    commandId: string,
    showUI?: boolean,
    value?: string
  ) => boolean;

  beforeEach(() => {
    execCommand = document.execCommand;
    document.execCommand = vi.fn();
  });

  afterEach(() => {
    document.execCommand = execCommand;
  });

  it("can copy a value", async () => {
    renderWithProviders(<CopyButton value="Test key" />);

    await userEvent.click(screen.getByRole("button"));

    expect(document.execCommand).toHaveBeenCalled();
  });
});
