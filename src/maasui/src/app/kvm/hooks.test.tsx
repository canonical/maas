import type { ReactNode } from "react";

import { renderHook } from "@testing-library/react";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router";
import configureStore from "redux-mock-store";
import type { MockStoreEnhanced } from "redux-mock-store";

import { useActivePod, useKVMDetailsRedirect } from "./hooks";

import urls from "@/app/base/urls";
import { podActions } from "@/app/store/pod";
import { PodType } from "@/app/store/pod/constants";
import * as factory from "@/testing/factories";

const mockStore = configureStore();

const generateWrapper =
  (store: MockStoreEnhanced<unknown>, pathname = "") =>
  ({ children }: { children: ReactNode }) => (
    <Provider store={store}>
      <MemoryRouter initialEntries={[{ pathname }]}>{children}</MemoryRouter>
    </Provider>
  );

describe("kvm hooks", () => {
  describe("useActivePod", () => {
    it("gets and sets active pod", () => {
      const state = factory.rootState();
      const store = mockStore(state);
      const podId = 1;
      renderHook(
        () => {
          useActivePod(podId);
        },
        {
          wrapper: generateWrapper(store),
        }
      );

      const expectedActions = [
        podActions.get(podId),
        podActions.setActive(podId),
      ];
      const actualActions = store.getActions();
      expectedActions.forEach((expectedAction) => {
        expect(
          actualActions.find(
            (actualAction) => actualAction.type === expectedAction.type
          )
        ).toStrictEqual(expectedAction);
      });
    });

    it("unsets active pod on unmount", () => {
      const state = factory.rootState();
      const store = mockStore(state);
      const podId = 1;
      const { unmount } = renderHook(
        () => {
          useActivePod(podId);
        },
        {
          wrapper: generateWrapper(store),
        }
      );
      unmount();

      const expectedAction = podActions.setActive(null);
      const setActiveActions = store
        .getActions()
        .filter((action) => action.type === expectedAction.type);
      // The setActive action is also used to unset the active pod, so we check
      // the second instance.
      expect(setActiveActions[1]).toStrictEqual(expectedAction);
    });

    it("does not dispatch actions if null id provided", () => {
      const state = factory.rootState();
      const store = mockStore(state);
      renderHook(
        () => {
          useActivePod(null);
        },
        {
          wrapper: generateWrapper(store),
        }
      );

      expect(store.getActions()).toStrictEqual([]);
    });
  });

  describe("useKVMDetailsRedirect", () => {
    it("returns null if pods have not yet loaded", () => {
      const state = factory.rootState({
        pod: factory.podState({ loaded: false }),
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useKVMDetailsRedirect(1), {
        wrapper: generateWrapper(store),
      });

      expect(result.current).toBe(null);
    });

    it("can redirect to cluster host page", () => {
      const state = factory.rootState({
        pod: factory.podState({
          items: [factory.pod({ cluster: 2, id: 1, type: PodType.LXD })],
          loaded: true,
        }),
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useKVMDetailsRedirect(1), {
        // Set the URL to the LXD single host settings page, but it's actually
        // in a cluster.
        wrapper: generateWrapper(store, urls.kvm.lxd.single.edit({ id: 1 })),
      });

      expect(result.current).toBe(
        urls.kvm.lxd.cluster.host.edit({ clusterId: 2, hostId: 1 })
      );
    });

    it("can redirect to LXD single host page", () => {
      const state = factory.rootState({
        pod: factory.podState({
          items: [factory.pod({ id: 1, type: PodType.LXD })],
          loaded: true,
        }),
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useKVMDetailsRedirect(1), {
        // Set the URL to virsh details, but it's actually a LXD single host.
        wrapper: generateWrapper(
          store,
          urls.kvm.virsh.details.index({ id: 1 })
        ),
      });

      expect(result.current).toBe(urls.kvm.lxd.single.index({ id: 1 }));
    });

    it("can redirect to Virsh page", () => {
      const state = factory.rootState({
        pod: factory.podState({
          items: [factory.pod({ id: 1, type: PodType.VIRSH })],
          loaded: true,
        }),
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useKVMDetailsRedirect(1), {
        // Set the URL to LXD single settings, but it's actually a virsh host
        wrapper: generateWrapper(store, urls.kvm.lxd.single.index({ id: 1 })),
      });

      expect(result.current).toBe(urls.kvm.virsh.details.index({ id: 1 }));
    });
  });
});
