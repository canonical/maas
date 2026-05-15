it("should verify that the element is disabled via aria-disabled attribute", () => {
  const element = document.createElement("button");
  expect(element).not.toBeAriaDisabled();
  element.setAttribute("aria-disabled", "true");
  expect(element).toBeAriaDisabled();
});
