declare namespace globalThis {
  // This *has* to be a var, otherwise it will not be included in the global scope
  // eslint-disable-next-line no-var
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}
