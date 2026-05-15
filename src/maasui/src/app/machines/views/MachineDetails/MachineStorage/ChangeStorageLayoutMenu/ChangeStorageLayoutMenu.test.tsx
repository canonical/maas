import ChangeStorageLayoutMenu, {
  storageLayoutOptions,
} from "./ChangeStorageLayoutMenu";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

let state: RootState;

beforeAll(() => {
  state = factory.rootState({
    machine: factory.machineState({
      items: [factory.machineDetails({ system_id: "abc123" })],
      statuses: factory.machineStatuses({
        abc123: factory.machineStatus(),
      }),
    }),
  });
});

it("renders", () => {
  renderWithProviders(<ChangeStorageLayoutMenu systemId="abc123" />, {
    state,
  });

  expect(
    screen.getByRole("button", { name: "Change storage layout" })
  ).toBeInTheDocument();
});

it("displays sub options when clicked", async () => {
  const testStorageOptions = storageLayoutOptions[0];
  renderWithProviders(<ChangeStorageLayoutMenu systemId="abc123" />, {
    state,
  });

  const storageBtn = screen.getByRole("button", {
    name: "Change storage layout",
  });
  await userEvent.click(storageBtn);
  testStorageOptions.forEach((option) => {
    expect(screen.getByRole("button", { name: option.label }));
  });
});
