import type { Message } from "@/app/store/message/types";
import type { RootState } from "@/app/store/root/types";

/**
 * Get the global messages.
 * @param {RootState} state - The redux state.
 * @returns {Message[]} The list of messages.
 */
const all = (state: RootState): Message[] => state.message.items;

const count = (state: RootState): number => state.message.items.length;

const messages = { all, count };

export default messages;
