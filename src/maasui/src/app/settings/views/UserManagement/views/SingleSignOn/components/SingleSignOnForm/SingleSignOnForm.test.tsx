import { waitFor } from "@testing-library/react";

import SingleSignOnForm from "./SingleSignOnForm";

import type { OAuthProviderResponse } from "@/app/apiclient";
import { oAuthProviderFactory } from "@/testing/factories/auth";
import { authResolvers } from "@/testing/resolvers/auth";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
} from "@/testing/utils";

let mockAuthProvider: OAuthProviderResponse;

const mockServer = setupMockServer(
  authResolvers.createOauthProvider.handler(),
  authResolvers.updateOauthProvider.handler()
);

describe("SingleSignOnForm", () => {
  const maasURL = "http://example.com/maas";
  beforeEach(() => {
    mockAuthProvider = oAuthProviderFactory.build();
  });

  afterEach(() => {
    authResolvers.createOauthProvider.resolved = false;
    authResolvers.updateOauthProvider.resolved = false;
  });

  it("doesn't pre-fill the data if no provider is present", () => {
    renderWithProviders(
      <SingleSignOnForm maasURL={maasURL} provider={undefined} />
    );

    expect(screen.getByRole("textbox", { name: /Name/i })).toHaveValue("");
    expect(screen.getByRole("textbox", { name: /Client ID/i })).toHaveValue("");
    expect(screen.getByRole("textbox", { name: /Client secret/i })).toHaveValue(
      ""
    );
    expect(screen.getByRole("textbox", { name: /Issuer URL/i })).toHaveValue(
      ""
    );
    // Redirect URI should be pre-filled as the default callback url
    expect(screen.getByRole("textbox", { name: /Redirect URI/i })).toHaveValue(
      maasURL + "/r/login/oidc/callback"
    );
    expect(screen.getByRole("textbox", { name: /Scopes/i })).toHaveValue("");
    expect(screen.getByRole("combobox", { name: /Token type/i })).toHaveValue(
      "JWT"
    );
  });

  it("pre-fills the data if a provider is present", () => {
    renderWithProviders(
      <SingleSignOnForm maasURL={maasURL} provider={mockAuthProvider} />
    );

    expect(screen.getByRole("textbox", { name: /Name/i })).toHaveValue(
      mockAuthProvider.name
    );
    expect(screen.getByRole("textbox", { name: /Client ID/i })).toHaveValue(
      mockAuthProvider.client_id
    );
    expect(screen.getByRole("textbox", { name: /Client secret/i })).toHaveValue(
      mockAuthProvider.client_secret
    );
    expect(screen.getByRole("textbox", { name: /Issuer URL/i })).toHaveValue(
      mockAuthProvider.issuer_url
    );
    expect(screen.getByRole("textbox", { name: /Redirect URI/i })).toHaveValue(
      mockAuthProvider.redirect_uri
    );
    expect(screen.getByRole("textbox", { name: /Scopes/i })).toHaveValue(
      mockAuthProvider.scopes
    );
    expect(screen.getByRole("combobox", { name: /Token type/i })).toHaveValue(
      mockAuthProvider.token_type
    );
  });

  it("calls the endpoint to create a provider if one is not given as a prop", async () => {
    renderWithProviders(
      <SingleSignOnForm maasURL={maasURL} provider={undefined} />
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: /Name/i }),
      mockAuthProvider.name
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /Client ID/i }),
      mockAuthProvider.client_id
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /Client secret/i }),
      mockAuthProvider.client_secret
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /Issuer URL/i }),
      mockAuthProvider.issuer_url
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /Redirect URI/i }),
      mockAuthProvider.redirect_uri
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /Scopes/i }),
      mockAuthProvider.scopes
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /Token type/i }),
      mockAuthProvider.token_type
    );

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(authResolvers.createOauthProvider.resolved).toBe(true);
    });
    expect(authResolvers.updateOauthProvider.resolved).toBe(false);
  });

  it("calls the endpoint to update a provider if one is given as a prop", async () => {
    mockAuthProvider = oAuthProviderFactory.build({ name: "red hat" });

    renderWithProviders(
      <SingleSignOnForm maasURL={maasURL} provider={mockAuthProvider} />
    );

    await userEvent.clear(screen.getByRole("textbox", { name: /Name/i }));

    await userEvent.type(
      screen.getByRole("textbox", { name: /Name/i }),
      "canonical"
    );

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(authResolvers.updateOauthProvider.resolved).toBe(true);
    });
    expect(authResolvers.createOauthProvider.resolved).toBe(false);
  });

  it("displays error messages when submission fails for creating a provider", async () => {
    mockServer.use(
      authResolvers.createOauthProvider.error({
        message: "oh no",
        code: 500,
        kind: "Error",
      })
    );

    renderWithProviders(
      <SingleSignOnForm maasURL={maasURL} provider={undefined} />
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: /Name/i }),
      mockAuthProvider.name
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /Client ID/i }),
      mockAuthProvider.client_id
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /Client secret/i }),
      mockAuthProvider.client_secret
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /Issuer URL/i }),
      mockAuthProvider.issuer_url
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /Redirect URI/i }),
      mockAuthProvider.redirect_uri
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /Scopes/i }),
      mockAuthProvider.scopes
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /Token type/i }),
      mockAuthProvider.token_type
    );

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(authResolvers.createOauthProvider.resolved).toBe(true);
    });

    expect(screen.getByText("oh no")).toBeInTheDocument();
  });

  it("displays error messages when submission fails for creating a provider", async () => {
    mockServer.use(
      authResolvers.updateOauthProvider.error({
        message: "oh no",
        code: 500,
        kind: "Error",
      })
    );

    mockAuthProvider = oAuthProviderFactory.build({ name: "red hat" });

    renderWithProviders(
      <SingleSignOnForm maasURL={maasURL} provider={mockAuthProvider} />
    );

    await userEvent.clear(screen.getByRole("textbox", { name: /Name/i }));

    await userEvent.type(
      screen.getByRole("textbox", { name: /Name/i }),
      "canonical"
    );

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(authResolvers.updateOauthProvider.resolved).toBe(true);
    });

    expect(screen.getByText("oh no")).toBeInTheDocument();
  });

  it("clears the form when 'Cancel' is clicked", async () => {
    renderWithProviders(
      <SingleSignOnForm maasURL={maasURL} provider={undefined} />
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: /Name/i }),
      "canonical"
    );

    expect(screen.getByRole("textbox", { name: /Name/i })).toHaveValue(
      "canonical"
    );

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: /Name/i })).toHaveValue("");
    });
  });

  it("resets the form to an empty state if 'provider' becomes undefined", async () => {
    const { rerender } = renderWithProviders(
      <SingleSignOnForm maasURL={maasURL} provider={mockAuthProvider} />
    );

    expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue(
      mockAuthProvider.name
    );

    rerender(<SingleSignOnForm maasURL={maasURL} provider={undefined} />);

    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue("");
      expect(
        screen.getByRole("textbox", { name: /Redirect URI/i })
      ).toHaveValue(maasURL + "/r/login/oidc/callback");
    });
  });
});
