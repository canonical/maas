import { createSlice } from "@reduxjs/toolkit";
import type { PayloadAction } from "@reduxjs/toolkit";

import { MessageMeta } from "./types";
import type { Message, MessageState } from "./types";

let messageId = 0;

const getMessageId = () => {
  messageId++;
  return messageId;
};

const messageSlice = createSlice({
  name: MessageMeta.MODEL,
  initialState: {
    items: [],
  } as MessageState,
  reducers: {
    add: {
      prepare: (
        message: Message["message"],
        severity?: Message["severity"],
        title?: Message["title"],
        temporary = true
      ) => ({
        payload: {
          id: getMessageId(),
          message,
          severity,
          temporary,
          title,
        },
      }),
      reducer: (state: MessageState, action: PayloadAction<Message>) => {
        state.items.push(action.payload);
      },
    },
    remove: {
      prepare: (id: Message[MessageMeta.PK]) => ({
        payload: id,
      }),
      reducer: (
        state: MessageState,
        action: PayloadAction<Message[MessageMeta.PK]>
      ) => {
        const index = state.items.findIndex(
          (item) => item.id === action.payload
        );
        state.items.splice(index, 1);
      },
    },
  },
});

export const { actions } = messageSlice;

export default messageSlice.reducer;
