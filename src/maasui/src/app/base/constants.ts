export const ACTION_STATUS = {
  error: "error",
  idle: "idle",
  loading: "loading",
  success: "success",
} as const;

export const COMMON_ACTIONS = {
  cleanup: "cleanup",
  create: "create",
  delete: "delete",
  fetch: "fetch",
  update: "update",
} as const;

export const COMMON_WEBSOCKET_METHODS = {
  create: "create",
  delete: "delete",
  list: "list",
  update: "update",
} as const;

/**
 * Common column sizes used in <Col> components
 */
export const COL_SIZES = {
  CARD_TITLE: 2,
  TABLE_CONFIRM_BUTTONS: 4,
  SIDEBAR: 3,
  TOTAL: 12,
} as const;

export const COLOURS = {
  CAUTION: "#F99B11",
  LIGHT: "#F7F7F7",
  LINK_FADED: "#D3E4ED",
  LINK: "#0066CC",
  NEGATIVE: "#C7162B",
  POSITIVE_FADED: "#B7CCB9",
  POSITIVE_MID: "#4DAB4D",
  POSITIVE: "#0E8420",
} as const;

// global keyboard shortcuts
export const KEYBOARD_SHORTCUTS = ["[", "/"] as const;
export type KeyboardShortcut = (typeof KEYBOARD_SHORTCUTS)[number];

export const DEFAULT_PAGE_SIZE = 50;
