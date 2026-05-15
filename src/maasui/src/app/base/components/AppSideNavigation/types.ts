export type NavItem = {
  adminOnly?: boolean;
  highlight?: string[] | string;
  label: string;
  url: string;
};

export type NavGroup = {
  navLinks: NavItem[];
  groupTitle?: string;
  groupIcon?: string;
};
