import type { ReactElement } from "react";

import APIKeyDeleteForm from "@/app/preferences/views/APIKeys/components/APIKeyDeleteForm/APIKeyDeleteForm";
import type { Token } from "@/app/store/token/types";
import { isId } from "@/app/utils";

const APIKeyDelete = ({ id }: { id: Token["id"] }): ReactElement => {
  if (!isId(id)) {
    return <h4>API Key not found</h4>;
  }

  return <APIKeyDeleteForm id={id} />;
};

export default APIKeyDelete;
