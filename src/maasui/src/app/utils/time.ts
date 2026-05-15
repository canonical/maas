import { formatDistance, parse } from "date-fns";
import { formatInTimeZone } from "date-fns-tz";

import type { UtcDatetime, UtcDatetimeDisplay } from "@/app/store/types/model";

const DATETIME_DISPLAY_FORMAT = "E, dd LLL. yyyy HH:mm:ss";

export const parseUtcDatetime = (utcTimeString: UtcDatetime): Date =>
  parse(
    `${utcTimeString} +00`, // let parse fn know it's UTC
    `${DATETIME_DISPLAY_FORMAT} x`,
    new Date()
  );

export const getTimeDistanceString = (utcTimeString: UtcDatetime): string =>
  formatDistance(parseUtcDatetime(utcTimeString), new Date(), {
    addSuffix: true,
  });

/**
 * @param utcTimeString - time string in UTC_DATETIME_FORMAT
 * @returns time string adjusted for local time zone in DATETIME_FORMAT
 */
export const formatUtcDatetime = (
  utcTimeString?: UtcDatetime
): UtcDatetimeDisplay => {
  if (!utcTimeString) return "Never";

  try {
    const utcTime = `${formatInTimeZone(
      parseUtcDatetime(utcTimeString),
      "UTC",
      DATETIME_DISPLAY_FORMAT,
      { addSuffix: true }
    )} (UTC)` as const;
    return utcTime;
  } catch {
    return "Never";
  }
};
