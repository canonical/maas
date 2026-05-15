import { useEffect, useRef, useState } from "react";

import type { SearchBoxProps } from "@canonical/react-components";
import { Icon } from "@canonical/react-components";
import classNames from "classnames";

import SearchBox from "@/app/base/components/SearchBox";

type Props = Omit<
  SearchBoxProps,
  "externallyControlled" | "onChange" | "ref" | "value"
> & {
  debounceInterval?: number;
  onDebounced: (debouncedText: string) => void;
  searchText: string;
  setSearchText: (searchText: string) => void;
  onChange?: SearchBoxProps["onChange"];
};

export const DEFAULT_DEBOUNCE_INTERVAL = 500;

export enum Labels {
  Loading = "Loading search results",
}

const DebounceSearchBox = ({
  debounceInterval = DEFAULT_DEBOUNCE_INTERVAL,
  onDebounced,
  onChange,
  searchText,
  setSearchText,
  ...props
}: Props): React.ReactElement => {
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const [debouncing, setDebouncing] = useState(false);

  // Clear the timeout when the component is unmounted.
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearTimeout(intervalRef.current);
      }
    };
  }, []);

  return (
    <div className="debounce-search-box">
      <SearchBox
        {...props}
        externallyControlled
        onChange={(text: string) => {
          onChange?.(text);
          setDebouncing(true);
          setSearchText(text);
          // Clear the previous timeout.
          if (intervalRef.current) {
            clearTimeout(intervalRef.current);
          }
          intervalRef.current = setTimeout(() => {
            onDebounced(text);
            setDebouncing(false);
          }, debounceInterval);
        }}
        value={searchText}
      />
      {debouncing && (
        <div
          aria-label={Labels.Loading}
          className={classNames(
            "debounce-search-box__spinner-container u-vertically-center",
            { "nudge-left": !!searchText }
          )}
          role="alert"
        >
          <Icon className="u-animation--spin" name="spinner" />
        </div>
      )}
    </div>
  );
};

export default DebounceSearchBox;
