import AddRecordForm, { Labels as AddRecordFormLabels } from "./AddRecordForm";

import { Labels as RecordFieldsLabels } from "@/app/domains/components/RecordFields/RecordFields";
import { RecordType } from "@/app/store/domain/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  renderWithProviders,
  mockSidePanel,
} from "@/testing/utils";

const { mockClose } = await mockSidePanel();

describe("AddRecordForm", () => {
  it("calls closeForm on cancel click", async () => {
    const state = factory.rootState({
      domain: factory.domainState({
        items: [factory.domain({ id: 1, name: "domain-in-the-brain" })],
      }),
    });

    renderWithProviders(<AddRecordForm id={1} />, {
      state,
    });
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("Dispatches the correct action on submit", async () => {
    const state = factory.rootState({
      domain: factory.domainState({
        items: [
          factory.domain({
            id: 1,
            name: "domain-in-the-brain",
            resource_count: 0,
          }),
        ],
      }),
    });

    const { store } = renderWithProviders(<AddRecordForm id={1} />, { state });

    await userEvent.type(
      screen.getByRole("textbox", { name: RecordFieldsLabels.Name }),
      "Some name"
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: RecordFieldsLabels.Type }),
      RecordType.CNAME
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: RecordFieldsLabels.Data }),
      "Some data"
    );

    await userEvent.type(
      screen.getByRole("spinbutton", { name: RecordFieldsLabels.Ttl }),
      "12"
    );

    await userEvent.click(
      screen.getByRole("button", { name: AddRecordFormLabels.SubmitLabel })
    );

    expect(
      store
        .getActions()
        .find((action) => action.type === "domain/createDNSData")
    ).toStrictEqual({
      type: "domain/createDNSData",
      meta: {
        method: "create_dnsdata",
        model: "domain",
      },
      payload: {
        params: {
          domain: 1,
          name: "Some name",
          rrtype: RecordType.CNAME,
          rrdata: "Some data",
          ttl: 12,
        },
      },
    });
  });
});
