import { useEffect, useState } from "react";

import { Link, Select } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import { useStorageState } from "react-storage-hooks";

import EventLogsTable from "./EventLogsTable";

import ArrowPagination from "@/app/base/components/ArrowPagination";
import { MAIN_CONTENT_SECTION_ID } from "@/app/base/components/MainContentSection/MainContentSection";
import SearchBox from "@/app/base/components/SearchBox";
import { useFetchActions } from "@/app/base/hooks";
import type { ControllerDetails } from "@/app/store/controller/types";
import { eventActions } from "@/app/store/event";
import eventSelectors from "@/app/store/event/selectors";
import type { EventRecord } from "@/app/store/event/types";
import type { MachineDetails } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";

type Props = {
  node: ControllerDetails | MachineDetails;
};

export enum Label {
  BackToTop = "Back to top",
  Title = "Event logs",
}

// The amount of events to preload. This is 1 more than would fit on a page so
// that the next page arrow appears.
const PRELOAD_COUNT = 201;

const filterEvents = (events: EventRecord[], searchText: string) => {
  const lowerSearchText = searchText?.toLowerCase();
  return lowerSearchText
    ? events.filter(
        (eventRecord) =>
          eventRecord.description?.toLowerCase().includes(lowerSearchText) ||
          eventRecord.type?.description?.toLowerCase().includes(lowerSearchText)
      )
    : [...events];
};

const getPageEvents = (
  events: EventRecord[],
  pageSize: number,
  startIndex: number
) => {
  return events
    .sort(
      (a: EventRecord, b: EventRecord) =>
        new Date(b.created).getTime() - new Date(a.created).getTime()
    )
    .slice(startIndex, startIndex + pageSize);
};

const EventLogs = ({ node }: Props): React.ReactElement => {
  const [searchText, setSearchText] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [requestedCount, setRequestedCount] = useState(false);
  const [lastRequested, setLastRequested] = useState<number | null>(null);
  const dispatch = useDispatch();
  const events = useSelector((state: RootState) =>
    eventSelectors.getByNodeId(state, node.id)
  );
  const loading = useSelector(eventSelectors.loading);
  const [pageSize, setPageSize] = useStorageState(
    localStorage,
    "eventLogPageSize",
    25
  );
  const unpaginatedEvents = filterEvents(events, searchText);
  const startIndex = (currentPage - 1) * pageSize;
  if (startIndex > unpaginatedEvents.length) {
    // If the rows have changed e.g. when filtering and the user is on a page
    // that no longer exists then send them to the start.
    setCurrentPage(1);
  }
  const paginatedEvents = getPageEvents(
    unpaginatedEvents,
    pageSize,
    startIndex
  );
  // Check the number of events on this page not the page size in case there are
  // less items.
  const showBackToTop = paginatedEvents.length >= 50;

  useFetchActions([() => eventActions.fetch(node.id, PRELOAD_COUNT)]);

  useEffect(() => {}, [
    dispatch,
    events,
    node,
    requestedCount,
    setRequestedCount,
  ]);

  useEffect(() => {
    const onLastPage =
      events.length === 0 ||
      currentPage === Math.ceil(events.length / pageSize);
    const lastItem = events[events.length - 1];
    const alreadyRequested = events.length && lastRequested === lastItem.id;
    // There's no need to fetch more events if the initial preload hasn't
    // happend or if it returned less events than requested.
    const initialEventsLoaded = events.length >= PRELOAD_COUNT;

    // Once the last page is reached then fetch more events.
    if (node && initialEventsLoaded && onLastPage && !alreadyRequested) {
      dispatch(eventActions.fetch(node.id, PRELOAD_COUNT, lastItem.id));
      setLastRequested(lastItem.id);
    }
  }, [
    dispatch,
    node,
    currentPage,
    events,
    lastRequested,
    pageSize,
    setLastRequested,
  ]);

  return (
    <div aria-label={Label.Title}>
      <div className="u-flex">
        <div className="u-flex--grow">
          <SearchBox
            onChange={setSearchText}
            placeholder="Search event logs"
            value={searchText}
          />
        </div>
        <ArrowPagination
          className="u-display--inline-block u-nudge-right"
          currentPage={currentPage}
          itemCount={unpaginatedEvents.length}
          pageSize={pageSize}
          setCurrentPage={setCurrentPage}
        />
        <Select
          defaultValue={pageSize.toString()}
          name="page-size"
          onChange={(evt: React.ChangeEvent<HTMLSelectElement>) => {
            setPageSize(Number(evt.target.value));
          }}
          options={[
            {
              value: "25",
              label: "25/page",
            },
            {
              value: "50",
              label: "50/page",
            },
            {
              value: "100",
              label: "100/page",
            },
            {
              value: "200",
              label: "200/page",
            },
          ]}
          wrapperClassName="u-display--inline-block u-nudge-right"
        />
      </div>
      <hr />
      <EventLogsTable events={paginatedEvents} loading={loading} />
      {showBackToTop && (
        <Link data-testid="backToTop" href={`#${MAIN_CONTENT_SECTION_ID}`} top>
          {Label.BackToTop}
        </Link>
      )}
    </div>
  );
};

export default EventLogs;
