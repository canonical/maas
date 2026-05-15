import type { Duration } from "date-fns";
import {
  add,
  differenceInSeconds,
  secondsToMinutes,
  intervalToDuration,
} from "date-fns";
import humanInterval from "human-interval";

import type { Minutes, Seconds, TimeSpan } from "@/app/base/types";

export const timeSpanToDuration = (timeSpan: TimeSpan | null): Duration => {
  if (!timeSpan) {
    return {};
  }
  return {
    hours:
      Number(/([\d]+)\s*(?:hs?|hours?)\s*/.exec(timeSpan)?.[1]) || undefined,
    minutes:
      Number(/([\d]+)\s*(?:ms?|mins?|minutes?)\s*/.exec(timeSpan)?.[1]) ||
      undefined,
    seconds:
      Number(/([\d]+)\s*(?:s|secs?|seconds?)\s*/.exec(timeSpan)?.[1]) ||
      undefined,
  };
};

const durationToSeconds = (duration: Duration): Seconds => {
  const now = new Date();
  return differenceInSeconds(add(now, duration), now);
};

const durationToMinutes = (duration: Duration): Minutes => {
  const now = new Date();
  return secondsToMinutes(differenceInSeconds(add(now, duration), now));
};

export const timeSpanToSeconds = (timeSpan: TimeSpan | null): Seconds =>
  durationToSeconds(timeSpanToDuration(timeSpan));

export const timeSpanToMinutes = (timeSpan: TimeSpan | null): Minutes =>
  durationToMinutes(timeSpanToDuration(timeSpan));

export const secondsToDuration = (seconds: number | undefined): Duration => {
  const now = new Date().getUTCDate();
  return intervalToDuration({
    start: now,
    end: add(now, { seconds: seconds }),
  });
};

export const humanReadableToSeconds = (
  humanTime: string
): number | undefined => {
  const millis = humanInterval(humanTime);
  return millis ? millis / 1000 : undefined;
};
