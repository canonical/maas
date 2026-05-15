import { useMemo, type ReactNode } from "react";

import type { ChipProps } from "@canonical/react-components";
import {
  Button,
  Col,
  Icon,
  ModularTable,
  Row,
} from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";
import { Link } from "react-router";
import type { ColumnWithLooseAccessor } from "react-table";

import TagChip from "../TagChip";
import { useSelectedTags, useUnchangedTags } from "../hooks";
import type { TagFormValues } from "../types";

import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import urls from "@/app/base/urls";
import type { MachineActionFormProps } from "@/app/machines/types";
import type { TagIdCountMap } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import tagSelectors from "@/app/store/tag/selectors";
import type { Tag, TagMeta } from "@/app/store/tag/types";
import { getTagCounts } from "@/app/store/tag/utils";
import { toFormikNumber } from "@/app/utils";

type Props = Pick<MachineActionFormProps, "selectedCount"> & {
  tags: Tag[];
  newTags: Tag[TagMeta.PK][];
  toggleTagDetails: (tag: Tag | null) => void;
};

export enum Label {
  Added = "To be added",
  Automatic = "Automatic tags",
  Discard = "Discard",
  Manual = "Currently assigned",
  Remove = "Remove",
  Removed = "To be removed",
  Table = "Tag changes",
  NoTags = "No tags are currently assigned to the selected machines.",
}

export enum RowType {
  Added = "added",
  Auto = "auto",
  Manual = "manual",
  Removed = "removed",
}

export enum Column {
  Action = "action",
  Label = "label",
  Name = "name",
  Options = "options",
}

type LabelCol = {
  children?: ReactNode;
  rowSpan?: number;
  row: {
    "aria-label": Label;
    "data-testid": RowType;
  };
};

const generateRows = (
  rowType: string,
  tags: Tag[],
  machineCount: number,
  tagIdsAndCounts: TagIdCountMap | null,
  label: ReactNode,
  toggleTagDetails: (tag: Tag | null) => void,
  newTags: Tag[TagMeta.PK][],
  chipAppearance?: ChipProps["appearance"],
  onRemove?: (tag: Tag) => void,
  removeLabel?: ReactNode
) => {
  return tags.map((tag, i) => ({
    label: {
      children: i === 0 ? label : null,
      rowSpan: i === 0 ? tags.length : null,
      row: {
        "aria-label": tag.name,
        "data-testid": rowType,
      },
    },
    name: (
      <TagChip
        appearance={chipAppearance}
        lead={
          rowType === RowType.Added && newTags.includes(tag.id)
            ? "NEW"
            : undefined
        }
        machineCount={machineCount}
        onClick={() => {
          toggleTagDetails(tag);
        }}
        tag={tag}
        tagIdsAndCounts={tagIdsAndCounts}
      />
    ),
    options: tag.kernel_opts ? <Icon aria-label="ticked" name="tick" /> : null,
    action: (
      <Button
        appearance="base"
        className="is-dense u-no-margin u-no-padding"
        onClick={() => onRemove?.(tag)}
        type="button"
      >
        {removeLabel}
      </Button>
    ),
  }));
};

export const TagFormChanges = ({
  tags,
  selectedCount,
  newTags,
  toggleTagDetails,
}: Props): React.ReactElement | null => {
  const { setFieldValue, values } = useFormikContext<TagFormValues>();
  const tagIdsAndCounts = getTagCounts(tags);
  const tagIds = tagIdsAndCounts ? Array.from(tagIdsAndCounts?.keys()) : [];
  const automaticTags = useSelector((state: RootState) =>
    tagSelectors.getAutomaticByIDs(state, tagIds)
  );
  const allManualTags = useSelector((state: RootState) =>
    tagSelectors.getManualByIDs(state, tagIds)
  );
  const machineCount = selectedCount ?? 0;
  const manualTags = useUnchangedTags(allManualTags);
  const addedTags = useSelectedTags("added");
  const removedTags = useSelectedTags("removed");
  const hasAutomaticTags = automaticTags.length > 0;
  const hasManualTags = manualTags.length > 0;
  const hasAddedTags = addedTags.length > 0;
  const hasRemovedTags = removedTags.length > 0;

  const columns = useMemo(
    () => [
      {
        accessor: Column.Label,
        // The data for this column is supplied inside a children prop so that
        // the data can also return the appropriate rowspan (used in getCellProps).
        Cell: ({ value }: { value: LabelCol }) => value.children || null,
        className: "label-col",
        Header: "Tag changes",
      },
      {
        accessor: Column.Name,
        className: "name-col",
        Header: "Tag name",
      },
      {
        accessor: Column.Options,
        className: "options-col u-align-text--right",
        Header: "Kernel options",
      },
      {
        accessor: Column.Action,
        className: "action-col u-align-text--right u-no-padding--right",
        Header: "Action",
      },
    ],
    []
  );
  if (!hasAutomaticTags && !hasManualTags && !hasAddedTags && !hasRemovedTags) {
    return <p className="u-text--muted">{Label.NoTags}</p>;
  }

  addedTags.forEach((tag) => {
    // Added tags will be applied to all machines.
    tagIdsAndCounts?.set(tag.id, machineCount);
  });
  return (
    <Row>
      <Col size={12}>
        <ModularTable
          aria-label={Label.Table}
          className="tag-form__changes"
          columns={columns as ColumnWithLooseAccessor[]}
          data={[
            ...generateRows(
              RowType.Added,
              addedTags,
              machineCount,
              tagIdsAndCounts,
              Label.Added,
              toggleTagDetails,
              newTags,
              "positive",
              (tag) => {
                setFieldValue(
                  "added",
                  values.added.filter((id) => tag.id !== toFormikNumber(id))
                ).catch((reason: unknown) => {
                  throw new FormikFieldChangeError(
                    "added",
                    "setFieldValue",
                    reason as string
                  );
                });
              },
              <>
                <span className="u-nudge-left--small">{Label.Discard}</span>
                <Icon name="close" />
              </>
            ),
            ...generateRows(
              RowType.Removed,
              removedTags,
              machineCount,
              tagIdsAndCounts,
              Label.Removed,
              toggleTagDetails,
              newTags,
              "negative",
              (tag) => {
                setFieldValue(
                  "removed",
                  values.removed.filter((id) => tag.id !== toFormikNumber(id))
                ).catch((reason: unknown) => {
                  throw new FormikFieldChangeError(
                    "removed",
                    "setFieldValue",
                    reason as string
                  );
                });
              },
              <>
                <span className="u-nudge-left--small">{Label.Discard}</span>
                <Icon aria-hidden="true" name="close" />
              </>
            ),
            ...generateRows(
              RowType.Manual,
              manualTags,
              machineCount,
              tagIdsAndCounts,
              Label.Manual,
              toggleTagDetails,
              newTags,
              "information",
              (tag) => {
                setFieldValue(
                  "removed",
                  values.removed.concat([tag.id.toString()])
                ).catch((reason: unknown) => {
                  throw new FormikFieldChangeError(
                    "removed",
                    "setFieldValue",
                    reason as string
                  );
                });
              },
              <>
                <span className="u-nudge-left--small">{Label.Remove}</span>
                <Icon aria-hidden="true" name="delete" />
              </>
            ),
            ...generateRows(
              RowType.Auto,
              automaticTags,
              machineCount,
              tagIdsAndCounts,
              Label.Automatic,
              toggleTagDetails,
              newTags
            ),
          ]}
          getCellProps={(props) => {
            if (props.column.id === Column.Label) {
              if (props.value?.rowSpan) {
                // Apply the rowspan prop to those that provide the prop. This will
                // appear as the first row in each type of tag change.
                return { rowSpan: props.value?.rowSpan };
              }
              // Hide all other label columns as this space will be taken up by the
              // rowspan column.
              return { className: "p-table--cell-collapse" };
            }
            return {};
          }}
          getRowProps={(row) => row.values.label.row}
        />
        {hasAutomaticTags && (
          <p className="u-text--muted u-nudge-right--small">
            These tags cannot be unassigned. Go to the{" "}
            <Link to={urls.tags.index}>Tags tab</Link> to manage automatic tags.
          </p>
        )}
      </Col>
    </Row>
  );
};

export default TagFormChanges;
