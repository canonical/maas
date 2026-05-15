import { createContext } from "react";

// A simple map between unique keys and file strings.
const files = new Map();

// The store to pass to the React context.
export const fileContextStore = {
  /**
   * Add a file to the store.
   * @param key - A unique key to store the file with.
   * @param file The file string.
   */
  add: (key: string, file: string): void => {
    files.set(key, file);
  },
  /**
   * Get a file from the store.
   * @param key - The file's unique key.
   * @returns The file as a string.
   */
  get: (key: string): string => {
    return files.get(key);
  },
  /**
   * Remove a file from the store.
   * @param key - The file's unique key.
   */
  remove: (key: string): void => {
    files.delete(key);
  },
};

// The context to be used by the React context providers and consumers.
const FileContext = createContext(fileContextStore);

export default FileContext;
