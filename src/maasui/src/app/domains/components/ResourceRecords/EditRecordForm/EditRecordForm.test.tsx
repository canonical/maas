import EditRecordForm, { Labels } from "./EditRecordForm";

import { Labels as RecordFieldsLabels } from "@/app/domains/components/RecordFields/RecordFields";
import { domainActions } from "@/app/store/domain";
import { RecordType } from "@/app/store/domain/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  renderWithProviders,
  mockSidePanel,
} from "@/testing/utils";

const { mockClose } = await mockSidePanel();

describe("EditRecordForm", () => {
  let state: RootState;
  const resourceA = factory.domainResource({
    dnsdata_id: null,
    dnsresource_id: 11,
    name: "test-resource-A",
    rrdata: "0.0.0.0",
    rrtype: RecordType.A,
  });
  const resourceTXT = factory.domainResource({
    dnsdata_id: 22,
    dnsresource_id: 33,
    name: "test-resource-TXT",
    rrdata: "testing",
    rrtype: RecordType.TXT,
  });

  beforeEach(() => {
    state = factory.rootState({
      domain: factory.domainState({
        items: [
          factory.domainDetails({
            id: 1,
            name: "test",
            rrsets: [resourceA, resourceTXT],
          }),
        ],
      }),
    });
  });

  it("closes the form when Cancel button is clicked", async () => {
    renderWithProviders(<EditRecordForm id={1} resource={resourceA} />, {
      state,
    });

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(mockClose).toHaveBeenCalled();
  });

  it("dispatches an action to update the record", async () => {
    const { store } = renderWithProviders(
      <EditRecordForm id={1} resource={resourceA} />,
      {
        state,
      }
    );

    const dataInputField = screen.getByRole("textbox", {
      name: RecordFieldsLabels.Data,
    });

    await userEvent.clear(dataInputField);
    await userEvent.type(dataInputField, "testing");

    await userEvent.type(
      screen.getByRole("spinbutton", { name: RecordFieldsLabels.Ttl }),
      "42"
    );

    await userEvent.click(
      screen.getByRole("button", { name: Labels.SubmitLabel })
    );

    const expectedAction = domainActions.updateRecord({
      domain: 1,
      name: resourceA.name,
      rrdata: "testing",
      rrset: resourceA,
      ttl: 42,
    });

    const actualAction = store
      .getActions()
      .find((action) => action.type === "domain/updateRecord");
    expect(actualAction).toStrictEqual(expectedAction);
  });
});
