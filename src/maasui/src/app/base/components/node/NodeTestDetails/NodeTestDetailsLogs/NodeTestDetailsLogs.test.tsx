/* eslint-disable testing-library/no-container */
import NodeTestDetailsLogs from "./NodeTestDetailsLogs";

import * as factory from "@/testing/factories";
import { render, screen, userEvent } from "@/testing/utils";

describe("NodeTestDetailsLogs", () => {
  it("displays combined content by default", () => {
    const log = factory.scriptResultData();

    const { container } = render(<NodeTestDetailsLogs log={log} />);

    expect(container.querySelector("code")).toHaveTextContent(
      "combined content"
    );
  });

  it("displays other content on click", async () => {
    const log = factory.scriptResultData();

    const { container } = render(<NodeTestDetailsLogs log={log} />);
    await userEvent.click(screen.getByTestId("tab-link-yaml"));

    expect(container.querySelector("code")).toHaveTextContent("yaml result");
  });

  it("displays 'no data' for empty content", async () => {
    const log = factory.scriptResultData();

    const { container } = render(<NodeTestDetailsLogs log={log} />);
    await userEvent.click(screen.getByTestId("tab-link-stderr"));

    expect(container.querySelector("code")).toHaveTextContent("No data");
  });
});
