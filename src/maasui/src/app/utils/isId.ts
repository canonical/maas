export const isId = <I extends number | string>(id?: I | null): id is I => {
  return !!id || id === 0;
};
