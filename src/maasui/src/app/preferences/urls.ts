import type { Token } from "@/app/store/token/types";
import { argPath } from "@/app/utils";

const urls = {
  apiKeys: {
    add: "/account/prefs/api-keys/add",
    edit: argPath<{ id: Token["id"] }>("/account/prefs/api-keys/:id/edit"),
    delete: argPath<{ id: Token["id"] }>("/account/prefs/api-keys/:id/delete"),
    index: "/account/prefs/api-keys",
  },
  details: "/account/prefs/details",
  index: "/account/prefs",
  sshKeys: "/account/prefs/ssh-keys",
  sslKeys: "/account/prefs/ssl-keys",
};

export default urls;
