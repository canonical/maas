import { useRef } from "react";

import type { SearchBoxProps } from "@canonical/react-components";
import { SearchBox as BaseSearchBox } from "@canonical/react-components";

import { useGlobalKeyShortcut } from "@/app/base/hooks/base";

const SearchBox = (props: SearchBoxProps): React.ReactElement => {
  const searchBoxRef = useRef<HTMLInputElement>(null);

  useGlobalKeyShortcut("/", (e) => {
    e.preventDefault();
    searchBoxRef.current?.focus?.();
  });

  return <BaseSearchBox aria-label="Search" {...props} ref={searchBoxRef} />;
};

export default SearchBox;
