import React, { createContext } from "react";

import { websocketClient } from "@/redux-store";
import type WebSocketClient from "@/websocket-client";

export const WebSocketContext = createContext<WebSocketClient | null>(null);

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  return (
    <WebSocketContext.Provider value={websocketClient}>
      {children}
    </WebSocketContext.Provider>
  );
};
