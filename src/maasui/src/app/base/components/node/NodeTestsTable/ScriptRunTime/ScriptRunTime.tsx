import { useEffect, useRef, useState } from "react";

import { intervalToDuration, fromUnixTime } from "date-fns";
import pluralize from "pluralize";

import {
  ScriptResultStatus,
  ScriptResultEstimated,
} from "@/app/store/scriptresult/types";
import type { ScriptResult } from "@/app/store/scriptresult/types";

type Props = {
  scriptResult: ScriptResult;
};

// Add leading zeros to single digit numbers.
const zeroPad = (time?: number) => `0${time || "0"}`.slice(-2);

const getElapsedTime = (starttime: ScriptResult["starttime"]) => {
  const { days, hours, minutes, seconds } = intervalToDuration({
    start: starttime ? fromUnixTime(starttime) : Date.now(),
    end: Date.now(),
  });
  const elapsed = [];
  // Show the elapsed days if more than a day has elapsed.
  if (days) {
    elapsed.push(pluralize("day", days, true));
  }
  // Display time in the format hh:mm:ss.
  elapsed.push(`${hours}:${zeroPad(minutes)}:${zeroPad(seconds)}`);
  return elapsed.join(", ");
};

const ScriptRunTime = ({ scriptResult }: Props): React.ReactElement | null => {
  const [elapsedTime, setElapsedTime] = useState("");
  const timerId = useRef<NodeJS.Timeout>(null);
  const isInstalling = scriptResult.status === ScriptResultStatus.INSTALLING;
  const isPending = scriptResult.status === ScriptResultStatus.PENDING;
  const isRunning = scriptResult.status === ScriptResultStatus.RUNNING;
  const estimatedRuntimeKnown =
    scriptResult.estimated_runtime !== ScriptResultEstimated.UNKNOWN;

  useEffect(() => {
    if (isRunning || isInstalling) {
      // If an action is in process then update the elapsed time every second.
      setElapsedTime(getElapsedTime(scriptResult.starttime));
      timerId.current = setInterval(() => {
        setElapsedTime(getElapsedTime(scriptResult.starttime));
      }, 1000);
    }
    return () => {
      if (timerId.current) {
        clearInterval(timerId.current);
      }
    };
  }, [isRunning, isInstalling, scriptResult]);

  let runtime: string | null = null;
  if (isRunning || isInstalling) {
    if (estimatedRuntimeKnown) {
      runtime = `${elapsedTime} of ~${scriptResult.estimated_runtime}`;
    } else {
      runtime = elapsedTime;
    }
  } else if (isPending && estimatedRuntimeKnown) {
    runtime = `~${scriptResult.estimated_runtime}`;
  } else if (!isPending && !isRunning && !isInstalling) {
    runtime = scriptResult.runtime;
  }

  return <span>{runtime}</span>;
};

export default ScriptRunTime;
