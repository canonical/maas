import { generateEmptyStateMsg } from "./generateEmptyStateMsg";

it("returns default messages when custom messages are not provided", () => {
  const result = generateEmptyStateMsg("default");
  expect(result).toEqual("No data is available.");
});

it("returns a custom message when provided", () => {
  const customMessage = { default: "This is a message." };
  const result = generateEmptyStateMsg("default", customMessage);

  expect(result).toEqual(customMessage.default);
});
