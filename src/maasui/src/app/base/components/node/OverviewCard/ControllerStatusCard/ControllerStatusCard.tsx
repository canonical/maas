import type { ReactNode } from "react";
import { useEffect, useRef } from "react";

import { Icon, Spinner } from "@canonical/react-components";
import { nanoid } from "@reduxjs/toolkit";
import { useDispatch, useSelector } from "react-redux";

import TooltipButton from "@/app/base/components/TooltipButton";
import { controllerActions } from "@/app/store/controller";
import controllerSelectors from "@/app/store/controller/selectors";
import {
  ControllerInstallType,
  ImageSyncStatus,
} from "@/app/store/controller/types";
import type {
  ControllerVersions,
  ControllerDetails,
} from "@/app/store/controller/types";
import { isRack, isRegionAndRack } from "@/app/store/controller/utils";
import { useFormattedOS } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";

type Props = {
  controller: ControllerDetails;
};

export enum Labels {
  CheckingImages = "Checking images...",
  ImagesSynced = "Images synced",
  ImageSyncStatus = "Image sync status",
  NoStatus = "Asking for status...",
  Origin = "Origin",
  OSInfo = "OS info",
  RackTitle = "rackd",
  RegionRackTitle = "regiond + rackd",
  RegionTitle = "regiond",
  UnknownTitle = "Unknown node type",
  Version = "Version",
  VersionDetails = "Version details",
}

const getImageSyncStatus = (
  status: ImageSyncStatus | null,
  checkingImages: boolean
) => {
  let content: ReactNode;
  const showSpinner =
    checkingImages ||
    !status ||
    status === ImageSyncStatus.RegionImporting ||
    status === ImageSyncStatus.Syncing;
  if (showSpinner) {
    content = (
      <Spinner
        text={
          !status
            ? Labels.NoStatus
            : checkingImages
              ? Labels.CheckingImages
              : status
        }
      />
    );
  } else {
    content =
      status === ImageSyncStatus.Synced ? (
        <>
          <span className="u-nudge-left--small">{Labels.ImagesSynced}</span>
          <Icon aria-label={Labels.ImagesSynced} name="success" />
        </>
      ) : (
        status
      );
  }

  return (
    <p aria-label={Labels.ImageSyncStatus} className="u-sv-1">
      {content}
    </p>
  );
};

const getVersionDisplay = (versions: ControllerVersions) => {
  const { current, install_type, origin } = versions;
  const isDeb = install_type === ControllerInstallType.DEB;
  const isSnap = install_type === ControllerInstallType.SNAP;
  return (
    <>
      <span aria-label={Labels.Version}>
        Version: {current.version || "Unknown (less than 2.3.0)"}
      </span>
      <br />
      <span aria-label={Labels.Origin}>
        {isDeb ? "Deb" : isSnap ? "Channel" : "Origin"}: {origin || "Unknown"}
      </span>
    </>
  );
};

const ControllerStatusCard = ({ controller }: Props): React.ReactElement => {
  const dispatch = useDispatch();
  const pollId = useRef(nanoid());
  const status = useSelector((state: RootState) =>
    controllerSelectors.imageSyncStatusesForController(
      state,
      controller.system_id
    )
  );
  const checkingImages = useSelector((state: RootState) =>
    controllerSelectors.getStatusForController(
      state,
      controller.system_id,
      "checkingImages"
    )
  );
  const formattedOS = useFormattedOS(controller);

  useEffect(() => {
    const id = pollId.current;
    if (isRack(controller) || isRegionAndRack(controller)) {
      dispatch(controllerActions.pollCheckImages([controller.system_id], id));
    }
    return () => {
      dispatch(controllerActions.pollCheckImagesStop(id));
    };
  }, [dispatch, controller]);

  return (
    <>
      <div className="overview-card__status" data-testid="controller-status">
        <strong className="p-muted-heading u-no-padding--top">Overview</strong>
        <h4 className="u-no-margin--bottom">
          {controller.node_type_display}&nbsp;
          {controller.versions && (
            <TooltipButton
              aria-label={Labels.VersionDetails}
              message={getVersionDisplay(controller.versions)}
            />
          )}
        </h4>
        {isRack(controller) || isRegionAndRack(controller)
          ? getImageSyncStatus(status, checkingImages)
          : null}
        <p aria-label={Labels.OSInfo} className="u-text--muted">
          {formattedOS}
        </p>
      </div>
      <div className="overview-card__test-warning" />
    </>
  );
};

export default ControllerStatusCard;
