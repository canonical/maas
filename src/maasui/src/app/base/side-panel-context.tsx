import type { ComponentType, PropsWithChildren, ReactElement } from "react";
import { createContext, useCallback, useContext, useState } from "react";

// This new side panel context is meant to replace the old one over time. Since migrating all
// panels will take some time, these two contexts will live together while the migrations are
// being carried out.
// TODO: Once the migrations are complete, remove the old side panel context.

type SidePanelSize = "large" | "narrow" | "regular" | "wide";

interface SidePanelState<TProps = Record<string, unknown>> {
  isOpen: boolean;
  title: string;
  size: SidePanelSize;
  component: ComponentType<TProps> | null;
  props: TProps;
}

export interface SidePanelActions {
  openSidePanel: <
    TProps extends Record<string, unknown> = Record<string, unknown>,
  >(params: {
    component: ComponentType<TProps>;
    title: string;
    props?: TProps;
    size?: SidePanelSize;
  }) => void;
  closeSidePanel: () => void;
  setSidePanelSize: (size: SidePanelSize) => void;
}

type SidePanelContextValue = SidePanelActions & SidePanelState;

const SidePanelContext = createContext<SidePanelContextValue | null>(null);

/**
 * Hook for managing side panel state and actions.
 *
 * Provides methods to open/close side panels with React components and manages
 * panel size and visibility state.
 *
 * @returns Object containing:
 *   - `isOpen`: Boolean indicating if the side panel is currently open
 *   - `title`: Current panel title string
 *   - `size`: Current panel size ('narrow' | 'regular' | 'wide' | 'large')
 *   - `component`: Currently rendered component
 *   - `props`: Props passed to the current component
 *   - `openSidePanel({component, title, props?, size?})`: Opens panel with given component
 *   - `closeSidePanel()`: Closes the panel and resets state
 *   - `setSidePanelSize(size)`: Changes the panel width
 *
 * @throws Error when used outside SidePanelProvider
 *
 * @example
 * ```tsx
 * const { open, close, isOpen } = useSidePanel();
 *
 * // Open a panel with a form component
 * const handleEdit = (userId: number) => {
 *   open(EditUserForm, 'Edit User', { userId }, 'wide');
 * };
 *
 * // Close the panel
 * const handleCancel = () => {
 *   close();
 * };
 * ```
 */
export const useSidePanel = (): SidePanelContextValue => {
  const context = useContext(SidePanelContext);
  if (!context) {
    throw new Error("useSidePanel must be used within a SidePanelProvider");
  }
  return context;
};

const SidePanelContextProvider = ({
  children,
}: PropsWithChildren): ReactElement => {
  const [state, setState] = useState<SidePanelState>({
    isOpen: false,
    title: "",
    size: "regular",
    component: null,
    props: {},
  });

  const openSidePanel = <
    TProps extends Record<string, unknown> = Record<string, unknown>,
  >({
    component,
    title,
    props = {} as TProps,
    size = "regular",
  }: {
    component: ComponentType<TProps>;
    title: string;
    props?: TProps;
    size?: SidePanelSize;
  }) => {
    setState({
      isOpen: true,
      title,
      size,
      component: component as ComponentType<Record<string, unknown>>,
      props: props || ({} as Record<string, unknown>),
    });
  };

  const closeSidePanel = () => {
    setState({
      isOpen: false,
      title: "",
      size: "regular",
      component: null,
      props: {},
    });
  };

  const setSidePanelSize = useCallback((size: SidePanelSize) => {
    setState((prev) => ({ ...prev, size }));
  }, []);

  return (
    <SidePanelContext.Provider
      value={{
        ...state,
        openSidePanel,
        closeSidePanel,
        setSidePanelSize,
      }}
    >
      {children}
    </SidePanelContext.Provider>
  );
};

export default SidePanelContextProvider;
