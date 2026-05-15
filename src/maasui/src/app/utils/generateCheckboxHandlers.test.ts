import type { Mock } from "vitest";

import { generateCheckboxHandlers } from "./generateCheckboxHandlers";
import type { CheckboxHandlers } from "./generateCheckboxHandlers";

describe("generateCheckboxHandlers", () => {
  let onChange: Mock;
  let handlers: CheckboxHandlers<number>;
  type Selected = { system_id: number };
  let uniqueIdHandlers: CheckboxHandlers<Selected>;

  beforeEach(() => {
    onChange = vi.fn();
    handlers = generateCheckboxHandlers<number>((newIDs) => onChange(newIDs));
    uniqueIdHandlers = generateCheckboxHandlers<Selected>(
      (newIDs) => onChange(newIDs),
      ({ system_id }) => `unique-${system_id}`
    );
  });

  describe("handleGroupCheckbox", () => {
    it("runs onChange with all ids in a group if none already selected", () => {
      handlers.handleGroupCheckbox([3, 4], [1, 2]);
      expect(onChange).toHaveBeenCalledWith([1, 2, 3, 4]);
    });

    it("runs onChange to remove all ids in a group if at least one already selected", () => {
      handlers.handleGroupCheckbox([1, 2, 3], [3, 4]);
      expect(onChange).toHaveBeenCalledWith([4]);
    });

    it("runs onChange with all ids in a group if none already selected with generateUniqueId", () => {
      uniqueIdHandlers.handleGroupCheckbox(
        [{ system_id: 3 }, { system_id: 4 }],
        [{ system_id: 1 }, { system_id: 2 }]
      );
      expect(onChange).toHaveBeenCalledWith([
        { system_id: 1 },
        { system_id: 2 },
        { system_id: 3 },
        { system_id: 4 },
      ]);
    });

    it("runs onChange to remove all ids in a group if at least one already selected with generateUniqueId", () => {
      uniqueIdHandlers.handleGroupCheckbox(
        [{ system_id: 1 }, { system_id: 2 }, { system_id: 3 }],
        [{ system_id: 3 }, { system_id: 4 }]
      );
      expect(onChange).toHaveBeenCalledWith([{ system_id: 4 }]);
    });
  });

  describe("handleRowCheckbox", () => {
    it("runs onChange to add id if not already selected", () => {
      handlers.handleRowCheckbox(3, [1, 2]);
      expect(onChange).toHaveBeenCalledWith([1, 2, 3]);
    });

    it("runs onChange to remove id if already selected", () => {
      handlers.handleRowCheckbox(1, [1, 2]);
      expect(onChange).toHaveBeenCalledWith([2]);
    });

    it("runs onChange to add id if not already selected with generateUniqueId", () => {
      uniqueIdHandlers.handleRowCheckbox({ system_id: 3 }, [
        { system_id: 1 },
        { system_id: 2 },
      ]);
      expect(onChange).toHaveBeenCalledWith([
        { system_id: 1 },
        { system_id: 2 },
        { system_id: 3 },
      ]);
    });

    it("runs onChange to remove id if already selected with generateUniqueId", () => {
      uniqueIdHandlers.handleRowCheckbox({ system_id: 1 }, [
        { system_id: 1 },
        { system_id: 2 },
      ]);
      expect(onChange).toHaveBeenCalledWith([{ system_id: 2 }]);
    });
  });

  describe("checkSelected", () => {
    it("checks if a single id is selected", () => {
      expect(handlers.checkSelected(2, [1, 2])).toBe(true);
    });

    it("checks if a single id is not selected", () => {
      expect(handlers.checkSelected(3, [1, 2])).toBe(false);
    });

    it("checks if one of multiple ids is selected", () => {
      expect(handlers.checkSelected([2, 3], [1, 2])).toBe(true);
    });

    it("checks if multiple ids are not selected", () => {
      expect(handlers.checkSelected([3, 4], [1, 2])).toBe(false);
    });

    it("checks if a single id is selected with generateUniqueId", () => {
      expect(
        uniqueIdHandlers.checkSelected({ system_id: 2 }, [
          { system_id: 1 },
          { system_id: 2 },
        ])
      ).toBe(true);
    });

    it("checks if one of multiple ids is selected with generateUniqueId", () => {
      expect(
        uniqueIdHandlers.checkSelected(
          [{ system_id: 2 }, { system_id: 3 }],
          [{ system_id: 1 }, { system_id: 2 }]
        )
      ).toBe(true);
    });
  });

  describe("checkAllSelected", () => {
    it("checks if all ids are selected", () => {
      expect(handlers.checkAllSelected([2, 3], [3, 2])).toBe(true);
    });

    it("checks if some ids are not selected", () => {
      expect(handlers.checkAllSelected([2, 4], [1, 2])).toBe(false);
    });

    it("checks if all ids are selected with generateUniqueId", () => {
      expect(
        uniqueIdHandlers.checkAllSelected(
          [{ system_id: 2 }, { system_id: 3 }],
          [{ system_id: 3 }, { system_id: 2 }]
        )
      ).toBe(true);
    });
  });
});
