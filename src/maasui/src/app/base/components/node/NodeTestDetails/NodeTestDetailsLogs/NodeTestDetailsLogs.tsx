import { useState } from "react";

import { Code, Tabs } from "@canonical/react-components";

import type { ScriptResultData } from "@/app/store/scriptresult/types";
import { ScriptResultDataType } from "@/app/store/scriptresult/types";

type Props = {
  log: ScriptResultData;
};

const NodeTestDetailsLogs = ({ log }: Props): React.ReactElement => {
  const [activeTab, setActiveTab] =
    useState<keyof ScriptResultData>("combined");

  // Ideally should be buttons, see https://github.com/canonical/vanilla-framework/issues/3532
  const links = [
    ScriptResultDataType.COMBINED,
    ScriptResultDataType.STDOUT,
    ScriptResultDataType.STDERR,
    ScriptResultDataType.RESULT,
  ].map((tab) => ({
    active: activeTab === tab,
    label: tab === "result" ? "yaml" : tab,
    onClick: (e: React.MouseEvent) => {
      e.preventDefault();
      setActiveTab(tab);
    },
  }));

  const tabText = log[activeTab] || "";

  return (
    <>
      <Tabs links={links} />
      <Code className="u-no-margin--bottom" data-testid="log-content">
        {tabText === "" ? "No data" : tabText}
      </Code>
    </>
  );
};

export default NodeTestDetailsLogs;
