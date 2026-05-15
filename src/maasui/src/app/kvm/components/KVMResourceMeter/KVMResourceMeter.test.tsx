import { screen } from "@testing-library/react";

import KVMResourceMeter from "./KVMResourceMeter";

import { renderWithProviders } from "@/testing/utils";

describe("KVMResourceMeter", () => {
  it("can render a summary of the resource usage", () => {
    renderWithProviders(<KVMResourceMeter allocated={1} free={2} />);
    expect(screen.getByTestId("kvm-resource-summary")).toHaveTextContent(
      "1 of 3 allocated"
    );
    expect(
      screen.queryByTestId("kvm-resource-details")
    ).not.toBeInTheDocument();
  });

  it("can rendered a detailed version of the resource usage", () => {
    renderWithProviders(<KVMResourceMeter allocated={1} detailed free={2} />);
    expect(screen.getByTestId("kvm-resource-details")).toBeInTheDocument();
    expect(
      screen.queryByTestId("kvm-resource-summary")
    ).not.toBeInTheDocument();
  });

  it("renders other resource usage data if provided", () => {
    renderWithProviders(
      <KVMResourceMeter allocated={1} detailed free={2} other={3} />
    );
    expect(screen.getByTestId("kvm-resource-other")).toBeInTheDocument();
  });

  it("does not render other resource usage data if not provided", () => {
    renderWithProviders(<KVMResourceMeter allocated={1} detailed free={2} />);
    expect(screen.queryByTestId("kvm-resource-other")).not.toBeInTheDocument();
  });

  it("correctly formats non-binary units", () => {
    renderWithProviders(
      <KVMResourceMeter
        allocated={1000}
        detailed
        free={2000}
        other={4000}
        unit="B"
      />
    );
    expect(screen.getByTestId("kvm-resource-allocated")).toHaveTextContent(
      "1KB"
    );
    expect(screen.getByTestId("kvm-resource-free")).toHaveTextContent("2KB");
    expect(screen.getByTestId("kvm-resource-other")).toHaveTextContent("4KB");
  });

  it("correctly formats binary units", () => {
    renderWithProviders(
      <KVMResourceMeter
        allocated={1024}
        binaryUnit
        detailed
        free={2048}
        other={4096}
        unit="B"
      />
    );
    expect(screen.getByTestId("kvm-resource-allocated")).toHaveTextContent(
      "1KiB"
    );
    expect(screen.getByTestId("kvm-resource-free")).toHaveTextContent("2KiB");
    expect(screen.getByTestId("kvm-resource-other")).toHaveTextContent("4KiB");
  });
});
