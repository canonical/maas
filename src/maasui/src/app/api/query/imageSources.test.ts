import {
  useChangeImageSource,
  useFetchImageSource,
  useGetImageSource,
  useImageSources,
  useUpdateImageSource,
} from "./imageSources";

import type {
  BootSourceCreateRequest,
  BootSourceFetchRequest,
  BootSourceUpdateRequest,
} from "@/app/apiclient";
import {
  imageSourceResolvers,
  mockImageSources,
} from "@/testing/resolvers/imageSources";
import {
  renderHookWithProviders,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

const mockServer = setupMockServer(
  imageSourceResolvers.listImageSources.handler(),
  imageSourceResolvers.getImageSource.handler(),
  imageSourceResolvers.fetchImageSource.handler(),
  imageSourceResolvers.createImageSource.handler(),
  imageSourceResolvers.updateImageSource.handler(),
  imageSourceResolvers.deleteImageSource.handler()
);

describe("useImageSources", () => {
  it("should return image sources data", async () => {
    const { result } = renderHookWithProviders(() => useImageSources());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data?.items).toEqual(mockImageSources.items);
  });
});

describe("useGetImageSource", () => {
  it("should return the correct image source", async () => {
    const expectedImageSource = mockImageSources.items[0];
    const { result } = renderHookWithProviders(() =>
      useGetImageSource(
        { path: { boot_source_id: expectedImageSource.id } },
        true
      )
    );
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toMatchObject(expectedImageSource);
  });

  it("should return error if image source does not exist", async () => {
    const { result } = renderHookWithProviders(() =>
      useGetImageSource({ path: { boot_source_id: 99 } }, true)
    );
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });

  it("should not fetch when enabled is false", async () => {
    const { result } = renderHookWithProviders(() =>
      useGetImageSource({ path: { boot_source_id: 1 } }, false)
    );
    // Wait a bit to ensure the query doesn't start
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(result.current.isSuccess).toBe(false);
    expect(result.current.isLoading).toBe(false);
  });
});

describe("useChangeImageSource", () => {
  const newImageSource: BootSourceCreateRequest = {
    name: "Custom",
    url: "http://updated.images.io/",
    keyring_filename: "/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg",
    keyring_data: "newdata",
    priority: 5,
    skip_keyring_verification: false,
    enabled: true,
  };

  afterEach(() => {
    imageSourceResolvers.fetchImageSource.resolved = false;
    imageSourceResolvers.createImageSource.resolved = false;
    imageSourceResolvers.deleteImageSource.resolved = false;
  });

  it("should change an existing image source", async () => {
    const { result } = renderHookWithProviders(() => useChangeImageSource());
    result.current.mutate({
      body: {
        ...newImageSource,
        current_boot_source_id: 1,
      },
    });
    await waitFor(() => {
      expect(imageSourceResolvers.createImageSource.resolved).toBe(true);
    });
    await waitFor(() => {
      expect(imageSourceResolvers.deleteImageSource.resolved).toBe(true);
    });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it("should terminate if create fails", async () => {
    mockServer.use(imageSourceResolvers.createImageSource.error());
    const { result } = renderHookWithProviders(() => useChangeImageSource());
    result.current.mutate({
      body: {
        ...newImageSource,
        current_boot_source_id: 1,
      },
    });
    await waitFor(() => {
      expect(imageSourceResolvers.createImageSource.resolved).toBe(true);
    });
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
    expect(imageSourceResolvers.deleteImageSource.resolved).toBe(false);
  });
});

describe("useUpdateImageSource", () => {
  it("should update a source", async () => {
    const updatedImageSource: BootSourceUpdateRequest = {
      name: "Custom",
      url: "http://updated.images.io/",
      keyring_filename: "/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg",
      keyring_data: "newdata",
      priority: 5,
      skip_keyring_verification: false,
      enabled: true,
    };
    const { result } = renderHookWithProviders(() => useUpdateImageSource());
    result.current.mutate({
      body: updatedImageSource,
      path: { boot_source_id: 1 },
    });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useFetchImageSource", () => {
  it("should fetch the available images of the source", async () => {
    const newImageSource: BootSourceFetchRequest = {
      url: "http://updated.images.io/",
      keyring_filename: "/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg",
      keyring_data: "newdata",
      skip_keyring_verification: false,
    };
    const { result } = renderHookWithProviders(() => useFetchImageSource());
    result.current.mutate({
      body: newImageSource,
    });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});
