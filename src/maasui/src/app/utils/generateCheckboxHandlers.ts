import { arrayItemsEqual } from "./arrayItemsEqual";
import { someInArray } from "./someInArray";

export type CheckboxHandlers<ID> = {
  checkAllSelected: (rowIDs: ID[], selectedIDs: ID[]) => boolean;
  checkSelected: (rowIDs: ID | ID[], selectedIDs: ID[]) => boolean;
  handleGroupCheckbox: (ids: ID[], selectedIDs: ID[]) => void;
  handleRowCheckbox: (rowID: ID, selectedIDs: ID[]) => void;
};

/**
 * Generate checkbox handlers for use in tables.
 * @param {(newSelectedIDs: ID[]) => void} onChange - the function to run with the new list of IDs
 * @returns {CheckboxHandlers} Checkbox handlers object
 */
export const generateCheckboxHandlers = <ID>(
  onChange: (newSelectedIDs: ID[]) => void,
  generateUniqueId = (id: ID): unknown => id
): CheckboxHandlers<ID> => {
  // Handler to update a group of checkboxes (including all items in a table).
  const handleGroupCheckbox: CheckboxHandlers<ID>["handleGroupCheckbox"] = (
    ids,
    selectedIDs
  ) => {
    // Generate unique ids.
    const uniqueIds = ids.map((id: ID) => generateUniqueId(id));
    const uniqueSelectedIds = selectedIDs.map((id: ID) => generateUniqueId(id));
    // If some items in a group are already selected, remove all items in that group.
    // Otherwise add them to the selected array, without duplicates.
    const newSelectedIDs = someInArray(uniqueIds, uniqueSelectedIds)
      ? selectedIDs.filter((id) => !uniqueIds.includes(generateUniqueId(id)))
      : selectedIDs.concat(
          ids.filter((id) => !uniqueSelectedIds.includes(generateUniqueId(id)))
        );
    onChange(newSelectedIDs);
  };
  // Handler for checking whether a row is in the selected state.
  const checkSelected: CheckboxHandlers<ID>["checkSelected"] = (
    rowIDs,
    selectedIDs
  ) => {
    const rowIDsList = Array.isArray(rowIDs) ? rowIDs : [rowIDs];
    // Generate unique ids.
    const uniqueRowIDs = rowIDsList.map((id: ID) => generateUniqueId(id));
    const uniqueSelectedIds = selectedIDs.map((id: ID) => generateUniqueId(id));
    return someInArray(uniqueRowIDs, uniqueSelectedIds);
  };
  // Handler for checking whether all rows are in the selected state.
  const checkAllSelected: CheckboxHandlers<ID>["checkAllSelected"] = (
    rowIDs,
    selectedIDs
  ) => {
    // Generate unique ids.
    const uniqueRowIDs = rowIDs.map((id: ID) => generateUniqueId(id));
    const uniqueSelectedIds = selectedIDs.map((id: ID) => generateUniqueId(id));
    return arrayItemsEqual(uniqueRowIDs, uniqueSelectedIds);
  };
  // Handler to update a single checkbox.
  const handleRowCheckbox: CheckboxHandlers<ID>["handleRowCheckbox"] = (
    rowID,
    selectedIDs
  ) => {
    // If the item is selected, unselect it and vice versa.
    const newSelectedIDs = checkSelected(rowID, selectedIDs)
      ? selectedIDs.filter(
          (id) => generateUniqueId(id) !== generateUniqueId(rowID)
        )
      : [...selectedIDs, rowID];
    onChange(newSelectedIDs);
  };
  return {
    checkAllSelected,
    checkSelected,
    handleGroupCheckbox,
    handleRowCheckbox,
  };
};
