import type { ReactNode } from "react";

import * as reduxToolkit from "@reduxjs/toolkit";
import { renderHook } from "@testing-library/react";
import { Formik } from "formik";
import { Provider } from "react-redux";
import configureStore from "redux-mock-store";

import { useFetchTags, useSelectedTags, useUnchangedTags } from "./hooks";

import * as query from "@/app/store/machine/utils/query";
import { tagActions } from "@/app/store/tag";
import * as factory from "@/testing/factories";
import { waitFor } from "@/testing/utils";

const mockStore = configureStore();

describe("useSelectedTags", () => {
  it("gets tags that have been added", () => {
    const tags = [factory.tag(), factory.tag(), factory.tag()];
    const state = factory.rootState({
      tag: factory.tagState({
        items: tags,
        loading: false,
      }),
    });
    const store = mockStore(state);
    const { result } = renderHook(() => useSelectedTags("added"), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <Provider store={store}>
          <Formik
            initialValues={{ added: [tags[0].id, tags[2].id] }}
            onSubmit={vi.fn()}
          >
            {children}
          </Formik>
        </Provider>
      ),
    });
    expect(result.current).toStrictEqual([tags[0], tags[2]]);
  });

  it("gets tags that have been removed", () => {
    const tags = [factory.tag(), factory.tag(), factory.tag()];
    const state = factory.rootState({
      tag: factory.tagState({
        items: tags,
        loading: false,
      }),
    });
    const store = mockStore(state);
    const { result } = renderHook(() => useSelectedTags("removed"), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <Provider store={store}>
          <Formik
            initialValues={{ removed: [tags[0].id, tags[2].id] }}
            onSubmit={vi.fn()}
          >
            {children}
          </Formik>
        </Provider>
      ),
    });
    expect(result.current).toStrictEqual([tags[0], tags[2]]);
  });
});

describe("useUnchangedTags", () => {
  it("gets tags that have been added", () => {
    const tags = [
      factory.tag({ id: 1 }),
      factory.tag({ id: 2 }),
      factory.tag({ id: 3 }),
    ];
    const { result } = renderHook(() => useUnchangedTags(tags), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <Formik
          initialValues={{ added: [tags[0].id], removed: [tags[1].id] }}
          onSubmit={vi.fn()}
        >
          {children}
        </Formik>
      ),
    });
    expect(result.current).toStrictEqual([tags[2]]);
  });
});

describe("useFetchTags", () => {
  vi.mock("@reduxjs/toolkit", async () => {
    const actual: object = await vi.importActual("@reduxjs/toolkit");
    return {
      ...actual,
      nanoid: vi.fn(),
    };
  });

  beforeEach(() => {
    vi.spyOn(query, "generateCallId").mockReturnValue("mock-call-id");
    vi.spyOn(reduxToolkit, "nanoid").mockReturnValue("mock-call-id");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("cleans up request on unmount", async () => {
    const tags = [factory.tag(), factory.tag(), factory.tag()];
    const state = factory.rootState({
      tag: factory.tagState({
        items: tags,
        loading: false,
      }),
    });
    const store = mockStore(state);
    const { result, unmount } = renderHook(() => useFetchTags(), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <Provider store={store}>
          <Formik initialValues={{ added: [] }} onSubmit={vi.fn()}>
            {children}
          </Formik>
        </Provider>
      ),
    });
    await waitFor(() => {
      expect(result.current.callId).toStrictEqual("mock-call-id");
    });
    const expectedAction = tagActions.removeRequest(
      result.current.callId as string
    );
    const actualActions = store.getActions();
    unmount();
    expect(
      actualActions.find((action) => action.type === "tag/removeRequest")
    ).toStrictEqual(expectedAction);
  });
});
