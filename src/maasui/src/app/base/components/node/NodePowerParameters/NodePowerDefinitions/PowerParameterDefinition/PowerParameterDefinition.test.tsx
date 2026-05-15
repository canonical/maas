import PowerParameterDefinition from "./PowerParameterDefinition";

import { PowerFieldType } from "@/app/store/general/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

it("renders the value of a power parameter", () => {
  const field = factory.powerField({
    field_type: PowerFieldType.STRING,
  });
  renderWithProviders(
    <PowerParameterDefinition field={field} powerParameter="parameter" />
  );

  expect(screen.getByText(/parameter/)).toBeInTheDocument();
});

it("handles 'choice' power fields", () => {
  const field = factory.powerField({
    choices: [
      ["choice1", "Choice 1"],
      ["choice2", "Choice 2"],
    ],
    field_type: PowerFieldType.CHOICE,
  });
  renderWithProviders(
    <PowerParameterDefinition field={field} powerParameter="choice1" />
  );

  expect(screen.getByText(/Choice 1/)).toBeInTheDocument();
});

it("handles 'multiple_choice' power fields", () => {
  const field = factory.powerField({
    choices: [
      ["choice1", "Choice 1"],
      ["choice2", "Choice 2"],
      ["choice3", "Choice 3"],
    ],
    field_type: PowerFieldType.MULTIPLE_CHOICE,
  });
  renderWithProviders(
    <PowerParameterDefinition
      field={field}
      powerParameter={["choice1", "choice2"]}
    />
  );

  expect(screen.getByText(/Choice 1, Choice 2/)).toBeInTheDocument();
});

it("handles 'password' power fields", () => {
  const field = factory.powerField({
    field_type: PowerFieldType.PASSWORD,
  });
  renderWithProviders(
    <PowerParameterDefinition field={field} powerParameter="password" />
  );

  expect(screen.getByText("********")).toBeInTheDocument();
});
