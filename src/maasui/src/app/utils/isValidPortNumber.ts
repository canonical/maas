/**
 * Checks if a given port number is valid (between 0 and 65535).
 *
 * @param port The port number to check.
 * @returns True if valid, false otherwise.
 */
export const isValidPortNumber = (port: number): boolean => {
  return port >= 0 && port <= 65535;
};
