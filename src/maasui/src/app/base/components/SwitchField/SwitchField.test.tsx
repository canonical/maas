/* eslint-disable testing-library/no-container */
import SwitchField from "./SwitchField";

import { render } from "@/testing/utils";

describe("SwitchField", () => {
  it("can add additional classes", () => {
    const { container } = render(
      <SwitchField className="extra-class" type="text" />
    );
    const switchField = container.querySelector(".p-switch");
    expect(switchField).toHaveClass("p-form-validation__input");
    expect(switchField).toHaveClass("extra-class");
  });
});
