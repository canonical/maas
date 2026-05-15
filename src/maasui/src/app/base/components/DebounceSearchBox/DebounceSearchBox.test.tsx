import { useState } from "react";

import DebounceSearchBox, { Labels } from "./DebounceSearchBox";

import {
  userEvent,
  render,
  screen,
  waitFor,
  renderWithProviders,
} from "@/testing/utils";

describe("DebounceSearchBox", () => {
  it(`runs onDebounced fn when the search text changes via the input, after the
      debounce interval`, async () => {
    const onDebounced = vi.fn();
    const Proxy = () => {
      const [searchText, setSearchText] = useState("old-value");
      return (
        <DebounceSearchBox
          onDebounced={onDebounced}
          searchText={searchText}
          setSearchText={setSearchText}
        />
      );
    };
    renderWithProviders(<Proxy />);
    const searchBox = screen.getByRole("searchbox");

    await userEvent.clear(searchBox);
    await userEvent.type(searchBox, "new-value");

    await waitFor(() => {
      expect(onDebounced).toHaveBeenCalledWith("new-value");
    });
  });

  it(`does not run onDebounced fn when the search text changes via props, even
      after the debounce interval`, async () => {
    const onDebounced = vi.fn();
    const Proxy = ({ searchText }: { searchText: string }) => (
      <DebounceSearchBox
        onDebounced={onDebounced}
        searchText={searchText}
        setSearchText={vi.fn()}
      />
    );
    const { rerender } = render(<Proxy searchText="old-value" />);

    expect(onDebounced).not.toHaveBeenCalled();

    rerender(<Proxy searchText="new-value" />);
    expect(onDebounced).not.toHaveBeenCalled();
  });

  it("displays a spinner while debouncing search box input", async () => {
    renderWithProviders(
      <DebounceSearchBox
        onDebounced={vi.fn()}
        searchText="old-value"
        setSearchText={vi.fn()}
      />
    );
    const searchBox = screen.getByRole("searchbox");
    expect(
      screen.queryByRole("alert", { name: Labels.Loading })
    ).not.toBeInTheDocument();

    await userEvent.clear(searchBox);

    expect(
      screen.getByRole("alert", { name: Labels.Loading })
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.queryByRole("alert", { name: Labels.Loading })
      ).not.toBeInTheDocument();
    });
  });
});
