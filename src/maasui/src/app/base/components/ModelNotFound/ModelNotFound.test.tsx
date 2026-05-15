import ModelNotFound from "./ModelNotFound";

import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("ModelNotFound", () => {
  it("renders the correct heading", () => {
    const state = factory.rootState();
    renderWithProviders(
      <ModelNotFound id={1} linkURL="www.url.com" modelName="model" />,
      { state }
    );
    expect(screen.getByRole("heading").textContent).toBe("Model not found");
  });

  it("renders the default link correctly", () => {
    const state = factory.rootState();
    renderWithProviders(
      <ModelNotFound id={1} linkURL="/models" modelName="model" />,
      { state }
    );
    expect(
      screen.getByRole("link", { name: "View all models" })
    ).toHaveAttribute("href", "/models");
  });

  it("can be given customised link text", () => {
    const state = factory.rootState();
    renderWithProviders(
      <ModelNotFound
        id={1}
        linkText="Click here to win $500"
        linkURL="/models"
        modelName="model"
      />,
      { state }
    );
    expect(
      screen.getByRole("link", { name: "Click here to win $500" })
    ).toBeInTheDocument();
  });
});
