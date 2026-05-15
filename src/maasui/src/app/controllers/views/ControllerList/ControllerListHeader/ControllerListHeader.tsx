import { useEffect, useState } from "react";

import { MainToolbar } from "@canonical/maas-react-components";
import { Button, Spinner } from "@canonical/react-components";
import type { RowSelectionState } from "@tanstack/react-table";
import { useSelector } from "react-redux";

import DebounceSearchBox from "@/app/base/components/DebounceSearchBox";
import ModelListSubtitle from "@/app/base/components/ModelListSubtitle";
import NodeActionMenu from "@/app/base/components/NodeActionMenu";
import { useSendAnalytics } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { SetSearchFilter } from "@/app/base/types";
import AddController from "@/app/controllers/components/ControllerForms/AddController";
import ControllerActionFormWrapper from "@/app/controllers/components/ControllerForms/ControllerActionFormWrapper";
import controllerSelectors from "@/app/store/controller/selectors";
import type { ControllerActions } from "@/app/store/controller/types";
import { getNodeActionTitle } from "@/app/store/utils";

type Props = {
  rowSelection: RowSelectionState;
  searchFilter: string;
  setSearchFilter: SetSearchFilter;
};

const ControllerListHeader = ({
  rowSelection,
  searchFilter,
  setSearchFilter,
}: Props): React.ReactElement => {
  const controllers = useSelector(controllerSelectors.all);
  const controllersLoaded = useSelector(controllerSelectors.loaded);
  const selectedControllers = controllers.filter((controller) =>
    Object.keys(rowSelection).includes(controller.id.toString())
  );
  const sendAnalytics = useSendAnalytics();
  const [searchText, setSearchText] = useState(searchFilter);

  const { openSidePanel } = useSidePanel();

  useEffect(() => {
    // If the filters change then update the search input text.
    setSearchText(searchFilter);
  }, [searchFilter]);

  return (
    <MainToolbar>
      <MainToolbar.Title data-testid="section-header-title">
        Controllers
      </MainToolbar.Title>
      {controllersLoaded ? (
        <ModelListSubtitle
          available={controllers.length}
          filterSelected={() => {
            setSearchFilter("in:(Selected)");
          }}
          modelName="controller"
          selected={selectedControllers.length}
        />
      ) : (
        <Spinner text="Loading" />
      )}
      <MainToolbar.Controls>
        <DebounceSearchBox
          onDebounced={(debouncedText) => {
            setSearchFilter(debouncedText);
          }}
          searchText={searchText}
          setSearchText={setSearchText}
        />
        <Button
          data-testid="add-controller-button"
          disabled={selectedControllers.length > 0}
          onClick={() => {
            openSidePanel({
              component: AddController,
              title: "Add controller",
            });
          }}
        >
          Add rack controller
        </Button>
        <NodeActionMenu
          filterActions
          hasSelection={selectedControllers.length > 0}
          nodeDisplay="controller"
          nodes={selectedControllers}
          onActionClick={(action) => {
            const title = getNodeActionTitle(action);
            sendAnalytics("Controller list action form", title, "Open");
            openSidePanel({
              component: ControllerActionFormWrapper,
              props: {
                // action is a NodeAction, but is guarenteed to be a NodeAction that comprises ControllerActions.
                action: action as ControllerActions,
                controllers: selectedControllers,
                viewingDetails: false,
              },
              title,
            });
          }}
          showCount
        />
      </MainToolbar.Controls>
    </MainToolbar>
  );
};

export default ControllerListHeader;
