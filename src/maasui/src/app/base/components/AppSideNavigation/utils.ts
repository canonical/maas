import { matchPath } from "react-router";

import type { NavItem } from "./types";

export const isSelected = (path: string, link: NavItem): boolean => {
  // Use the provided highlight(s) or just use the url.
  let highlights = link.highlight || link.url;
  // If the provided highlights aren't an array then make them one so that we
  // can loop over them.
  if (!Array.isArray(highlights)) {
    highlights = [highlights];
  }
  // Check if one of the highlight urls matches the current path.
  return highlights.some((highlight) =>
    // Check the full path, for both legacy/new clients as sometimes the lists
    // are in one client and the details in the other.
    matchPath({ path: highlight, end: false }, path)
  );
};
