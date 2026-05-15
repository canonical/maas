import TagForm from "./TagForm";

import { Labels as EditableSectionLabels } from "@/app/base/components/EditableSection";
import urls from "@/app/base/urls";
import { Label as TagFormFieldsLabel } from "@/app/machines/components/MachineForms/MachineActionFormWrapper/TagForm/TagFormFields";
import { FilterMachines } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

describe("TagForm", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            permissions: ["edit"],
            system_id: "abc123",
            tags: [1, 2],
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
      tag: factory.tagState({
        items: [
          factory.tag({ id: 1, name: "tag-1" }),
          factory.tag({ id: 2, name: "tag-2" }),
        ],
        loaded: true,
      }),
    });
  });

  it("is not editable if machine does not have edit permission", () => {
    state.machine.items[0].permissions = [];
    renderWithProviders(<TagForm systemId="abc123" />, { state });

    expect(
      screen.queryByRole("button", { name: EditableSectionLabels.EditButton })
    ).not.toBeInTheDocument();
  });

  it("is editable if machine has edit permission", () => {
    state.machine.items[0].permissions = ["edit"];
    renderWithProviders(<TagForm systemId="abc123" />, { state });

    expect(
      screen.getAllByRole("button", { name: EditableSectionLabels.EditButton })
        .length
    ).not.toBe(0);
  });

  it("renders list of tag links until edit button is pressed", async () => {
    renderWithProviders(<TagForm systemId="abc123" />, { state });

    expect(screen.queryByLabelText("tag-form")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "tag-1" })).toHaveAttribute(
      "href",
      `${urls.machines.index}${FilterMachines.filtersToQueryString({
        tags: ["=tag-1"],
      })}`
    );
    expect(screen.getByRole("link", { name: "tag-2" })).toHaveAttribute(
      "href",
      `${urls.machines.index}${FilterMachines.filtersToQueryString({
        tags: ["=tag-2"],
      })}`
    );

    await userEvent.click(
      screen.getAllByRole("button", {
        name: EditableSectionLabels.EditButton,
      })[0]
    );

    expect(
      screen.getByRole("textbox", { name: TagFormFieldsLabel.TagInput })
    ).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
