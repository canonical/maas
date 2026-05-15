import TagChip from "./TagChip";

import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

const tags = [
  factory.tag({ name: "chip1", id: 1 }),
  factory.tag({ name: "chip2", id: 2 }),
];

const tagMap = new Map([
  [1, 2],
  [2, 1],
]);

it("displays chips with counts", () => {
  renderWithProviders(
    <TagChip machineCount={10} tag={tags[0]} tagIdsAndCounts={tagMap} />
  );
  expect(
    screen.getByRole("button", { name: "chip1 (2/10)" })
  ).toBeInTheDocument();
});
