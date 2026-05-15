import { useContext, useEffect, useRef } from "react";

import {
  ContextualMenu,
  NotificationSeverity,
} from "@canonical/react-components";
import { nanoid } from "@reduxjs/toolkit";
import { format } from "date-fns";
import fileDownload from "js-file-download";
import { useDispatch, useSelector } from "react-redux";

import { useGetInstallationOutput } from "../hooks";

import FileContext from "@/app/base/file-context";
import { useSendAnalytics } from "@/app/base/hooks";
import { api } from "@/app/base/sagas/http";
import { controllerActions } from "@/app/store/controller";
import type { ControllerDetails } from "@/app/store/controller/types";
import { machineActions } from "@/app/store/machine";
import type { MachineDetails } from "@/app/store/machine/types";
import { messageActions } from "@/app/store/message";
import type { RootState } from "@/app/store/root/types";
import scriptResultSelectors from "@/app/store/scriptresult/selectors";
import { ScriptResultNames } from "@/app/store/scriptresult/types";
import { NodeStatus } from "@/app/store/types/node";
import { nodeIsMachine } from "@/app/store/utils";
import { capitaliseFirst } from "@/app/utils";

type Props = {
  node: ControllerDetails | MachineDetails;
};

export enum Label {
  CurtinLogs = "curtin-logs.tar",
  InstallationOutput = "Installation output",
  Title = "Download menu",
  Toggle = "Download",
}

export const DownloadMenu = ({ node }: Props): React.ReactElement | null => {
  const dispatch = useDispatch();
  const installationResults = useSelector((state: RootState) =>
    scriptResultSelectors.getInstallationByNodeId(state, node.system_id)
  );
  // Only show the curtin log if the deployment has failed and there is a curtin
  // result.
  const showCurtinLog =
    node?.status === NodeStatus.FAILED_DEPLOYMENT &&
    installationResults?.some(
      ({ name }) => name === ScriptResultNames.CURTIN_LOG
    );
  const installationOutput = useGetInstallationOutput(node?.system_id);
  const getSummaryXmlKey = useRef(nanoid());
  const getSummaryYamlKey = useRef(nanoid());
  const fileContext = useContext(FileContext);
  const sendAnalytics = useSendAnalytics();
  const summaryXML = fileContext.get(getSummaryXmlKey.current);
  const summaryYAML = fileContext.get(getSummaryYamlKey.current);
  const today = format(new Date(), "yyyy-MM-dd");
  const toggleDisabled =
    !installationOutput?.log && !summaryYAML && !summaryXML;
  const isMachine = nodeIsMachine(node);
  const nodeLabel = isMachine ? "machine" : "controller";

  useEffect(() => {
    if (isMachine) {
      // Request the files for this machine.
      dispatch(
        machineActions.getSummaryXml({
          systemId: node.system_id,
          fileId: getSummaryXmlKey.current,
        })
      );
      dispatch(
        machineActions.getSummaryYaml({
          systemId: node.system_id,
          fileId: getSummaryYamlKey.current,
        })
      );
    } else {
      // Request the files for this controller.
      dispatch(
        controllerActions.getSummaryXml({
          systemId: node.system_id,
          fileId: getSummaryXmlKey.current,
        })
      );
      dispatch(
        controllerActions.getSummaryYaml({
          systemId: node.system_id,
          fileId: getSummaryYamlKey.current,
        })
      );
    }
  }, [dispatch, isMachine, node]);

  // Clean up the requested files when the component unmounts.
  useEffect(
    () => () => {
      fileContext.remove(getSummaryXmlKey.current);
      fileContext.remove(getSummaryYamlKey.current);
    },
    [fileContext]
  );

  const generateItem = (
    title: string,
    filename: string,
    extension: string,
    testKey: string,
    fileContent?: string | null
  ) => {
    if (!fileContent) {
      // If there is no file then return an empty array so it can be spread.
      return [];
    }
    return [
      {
        children: title,
        "data-testid": testKey,
        onClick: () => {
          if (fileContent && node) {
            fileDownload(
              fileContent,
              `${node.fqdn}-${filename}-${today}.${extension}`
            );
            sendAnalytics(
              `${nodeLabel} details logs`,
              "Download menu",
              `Download ${filename}.${extension}`
            );
          }
        },
      },
    ];
  };

  return (
    <div aria-label={Label.Title} className="download-menu">
      <ContextualMenu
        hasToggleIcon
        links={[
          ...generateItem(
            `${capitaliseFirst(nodeLabel)} output (YAML)`,
            `${nodeLabel}-output`,
            "yaml",
            `${nodeLabel}-output-yaml`,
            summaryYAML
          ),
          ...generateItem(
            `${capitaliseFirst(nodeLabel)} output (XML)`,
            `${nodeLabel}-output`,
            "xml",
            `${nodeLabel}-output-xml`,
            summaryXML
          ),
          ...(showCurtinLog
            ? [
                {
                  children: Label.CurtinLogs,
                  "data-testid": "curtin-logs",
                  onClick: () => {
                    api.scriptresults
                      .getCurtinLogsTar(node.system_id)
                      .then((response) => {
                        fileDownload(
                          response,
                          `${node.fqdn}-curtin-${today}.tar`
                        );
                      })
                      .catch((error: unknown) => {
                        dispatch(
                          messageActions.add(
                            `curtin.tar could not be downloaded: ${error as string}`,
                            NotificationSeverity.NEGATIVE
                          )
                        );
                      });
                    sendAnalytics(
                      `${nodeLabel} details logs`,
                      "Download menu",
                      "Download curtin-logs.tar"
                    );
                  },
                },
              ]
            : []),
          ...generateItem(
            Label.InstallationOutput,
            "installation-output",
            "log",
            "installation-output",
            installationOutput?.log
          ),
        ]}
        position="right"
        toggleDisabled={toggleDisabled}
        toggleLabel={Label.Toggle}
      />
    </div>
  );
};

export default DownloadMenu;
