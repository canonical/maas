import { useRef, useState } from "react";

import { Tooltip } from "@canonical/react-components";
import { nanoid } from "@reduxjs/toolkit";
import classNames from "classnames";

import useDarkMode from "../../hooks/useDarkMode/useDarkMode";

type Segment = {
  /**
   * The colour of the segment.
   */
  color: string;
  /**
   * The segment tooltip.
   */
  tooltip?: string;
  /**
   * The segment length.
   */
  value: number;
};

type Props = {
  /**
   * The label in the centre of the doughnut.
   */
  label?: string;
  /**
   * An optional class name applied to the wrapping element.
   */
  className?: string;
  /**
   * The width of the segments when hovered.
   */
  segmentHoverWidth: number;
  /**
   * The width of the segments.
   */
  segmentWidth: number;
  /**
   * The doughnut segments.
   */
  segments: Segment[];
  /**
   * The size of the doughnut.
   */
  size: number;
};

export enum TestIds {
  Label = "label",
  Segment = "segment",
}

export const DoughnutChart = ({
  className,
  label,
  segmentHoverWidth,
  segmentWidth,
  segments,
  size,
}: Props): React.ReactElement => {
  const [tooltipMessage, setTooltipMessage] = useState<
    Segment["tooltip"] | null
  >(null);

  const [isDarkMode] = useDarkMode();

  const id = useRef(`doughnut-chart-${nanoid()}`);
  const hoverIncrease = segmentHoverWidth - segmentWidth;
  const adjustedHoverWidth = segmentHoverWidth + hoverIncrease;
  // The canvas needs enough space so that the hover state does not get cut off.
  const canvasSize = size + adjustedHoverWidth - segmentWidth;
  const diameter = size - segmentWidth;
  const radius = diameter / 2;
  const circumference = Math.round(diameter * Math.PI);
  // Calculate the total value of all segments.
  const total = segments.reduce(
    (totalValue, segment) => (totalValue += segment.value),
    0
  );
  let accumulatedLength = 0;
  const segmentNodes = segments.map(({ color, tooltip, value }, i) => {
    // The start position is the value of all previous segments.
    const startPosition = accumulatedLength;
    // The length of the segment (as a portion of the doughnut circumference)
    const segmentLength = (value / total) * circumference;
    // The space left until the end of the circle.
    const remainingSpace = circumference - (segmentLength + startPosition);
    // Add this segment length to the running tally.
    accumulatedLength += segmentLength;
    return (
      <circle
        className="doughnut-chart__segment"
        cx={radius - segmentWidth / 2 - hoverIncrease}
        cy={radius + segmentWidth / 2 + hoverIncrease}
        data-testid={TestIds.Segment}
        key={i}
        onMouseOut={
          tooltip
            ? () => {
                // Hide the tooltip.
                setTooltipMessage(null);
              }
            : undefined
        }
        onMouseOver={
          tooltip
            ? () => {
                setTooltipMessage(tooltip);
              }
            : undefined
        }
        r={radius}
        style={{
          stroke: color,
          strokeWidth: segmentWidth,
          // The dash array used is:
          // 1 - We want there to be a space before the first visible dash so
          //     by setting this to 0 we can use the next dash for the space.
          // 2 - This gap is the distance of all previous segments
          //     so that the segment starts in the correct spot.
          // 3 - A dash that is the length of the segment.
          // 4 - A gap from the end of the segment to the start of the circle
          //     so that the dash array doesn't repeat and be visible.
          strokeDasharray: `0 ${startPosition.toFixed(
            2
          )} ${segmentLength.toFixed(2)} ${remainingSpace.toFixed(2)}`,
        }}
        // Rotate the segment so that the segments start at the top of
        // the chart.
        transform={`rotate(-90 ${radius},${radius})`}
      />
    );
  });
  return (
    <div
      className={classNames("doughnut-chart", className)}
      style={{ maxWidth: `${canvasSize}px` }}
    >
      <Tooltip
        className="doughnut-chart__tooltip"
        followMouse={true}
        message={tooltipMessage}
        position="right"
      >
        <style>
          {/* Set the hover width of the segments. */}
          {`#${id.current} .doughnut-chart__segment:hover {
          stroke-width: ${adjustedHoverWidth} !important;
        }`}
        </style>
        <svg
          className="doughnut-chart__chart"
          id={id.current}
          viewBox={`0 0 ${canvasSize} ${canvasSize}`}
        >
          <mask id="myMask">
            {/* Cover the canvas, this will be the visible area. */}
            <rect
              fill="white"
              height={canvasSize}
              width={canvasSize}
              x="0"
              y="0"
            />
            {/* Cut out the center circle so that the hover state doesn't grow inwards. */}
            <circle
              cx={canvasSize / 2}
              cy={canvasSize / 2}
              fill="black"
              r={radius - segmentWidth / 2}
            />
          </mask>
          <g mask="url(#myMask)">
            {/* Force the group to cover the full size of the canvas, otherwise it will only mask the children (in their non-hovered state) */}
            <rect
              fill="transparent"
              height={canvasSize}
              width={canvasSize}
              x="0"
              y="0"
            />
            <g>{segmentNodes}</g>
          </g>
          {label ? (
            <text
              fill={isDarkMode ? "white" : "black"}
              x={radius + adjustedHoverWidth / 2}
              y={radius + adjustedHoverWidth / 2}
            >
              <tspan
                className="doughnut-chart__label"
                data-testid={TestIds.Label}
              >
                {label}
              </tspan>
            </text>
          ) : null}
        </svg>
      </Tooltip>
    </div>
  );
};

export default DoughnutChart;
