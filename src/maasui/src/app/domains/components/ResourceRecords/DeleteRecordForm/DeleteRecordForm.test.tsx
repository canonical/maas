import DeleteRecordForm, {
  Labels as DeleteRecordFormLabels,
} from "./DeleteRecordForm";

import { domainActions } from "@/app/store/domain";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  renderWithProviders,
  mockSidePanel,
} from "@/testing/utils";

const { mockClose } = await mockSidePanel();

describe("DeleteRecordForm", () => {
  it("closes the form when Cancel button is clicked", async () => {
    const resource = factory.domainResource();
    const domain = factory.domainDetails({ id: 1, rrsets: [resource] });
    const state = factory.rootState({
      domain: factory.domainState({
        items: [domain],
      }),
    });

    renderWithProviders(
      <DeleteRecordForm id={domain.id} resource={resource} />,
      { state }
    );

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(mockClose).toHaveBeenCalled();
  });

  it("dispatches an action to delete one of many records that belong to a DNS resource", async () => {
    const [resource, otherResource] = [
      factory.domainResource({ dnsresource_id: 123, name: "resource" }),
      factory.domainResource({ dnsresource_id: 123, name: "other-resource" }),
    ];
    const domain = factory.domainDetails({
      id: 1,
      rrsets: [resource, otherResource],
    });
    const state = factory.rootState({
      domain: factory.domainState({
        items: [domain],
      }),
    });

    const { store } = renderWithProviders(
      <DeleteRecordForm id={1} resource={resource} />,
      {
        state,
      }
    );
    await userEvent.click(
      screen.getByRole("button", { name: DeleteRecordFormLabels.SubmitLabel })
    );

    const expectedAction = domainActions.deleteRecord({
      deleteResource: false,
      domain: domain.id,
      rrset: resource,
    });
    const actualAction = store
      .getActions()
      .find((action) => action.type === "domain/deleteRecord");
    expect(actualAction).toStrictEqual(expectedAction);
  });

  it("dispatches an action to delete the last record of a DNS resource", async () => {
    const resource = factory.domainResource();
    const domain = factory.domainDetails({ id: 1, rrsets: [resource] });
    const state = factory.rootState({
      domain: factory.domainState({
        items: [domain],
      }),
    });

    const { store } = renderWithProviders(
      <DeleteRecordForm id={1} resource={resource} />,
      {
        state,
      }
    );

    await userEvent.click(
      screen.getByRole("button", { name: DeleteRecordFormLabels.SubmitLabel })
    );

    const expectedAction = domainActions.deleteRecord({
      deleteResource: true,
      domain: domain.id,
      rrset: resource,
    });
    const actualAction = store
      .getActions()
      .find((action) => action.type === "domain/deleteRecord");
    expect(actualAction).toStrictEqual(expectedAction);
  });
});
