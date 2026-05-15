import {
  Button,
  CodeSnippet,
  Icon,
  Textarea,
} from "@canonical/react-components";
import fileDownload from "js-file-download";

import CopyButton from "@/app/base/components/CopyButton";
import type { CertificateData } from "@/app/store/general/types";

type Props = {
  certificate: CertificateData["certificate"];
  filename: string;
  isGenerated?: boolean;
};

export enum Labels {
  Download = "Download certificate",
}

export enum TestIds {
  CertCodeSnippet = "certificate-code-snippet",
  CertTextarea = "certificate-textarea",
}

const CertificateDownload = ({
  certificate,
  filename,
  isGenerated = false,
}: Props): React.ReactElement => {
  return (
    <>
      {isGenerated ? (
        <div className="certificate-download">
          <CodeSnippet
            blocks={[
              { code: `lxc config trust add - <<EOF\n\n${certificate}\nEOF` },
            ]}
            className="u-no-margin--bottom"
            data-testid={TestIds.CertCodeSnippet}
          />
        </div>
      ) : (
        <Textarea
          className="p-textarea--readonly"
          data-testid={TestIds.CertTextarea}
          id="lxd-cert"
          readOnly
          rows={5}
          value={certificate}
        />
      )}
      <Button
        onClick={() => {
          fileDownload(certificate, filename);
        }}
        type="button"
      >
        {Labels.Download}
        <span className="u-nudge-right--small">
          <Icon name="begin-downloading" />
        </span>
      </Button>
      <CopyButton
        value={`lxc config trust add - <<EOF \n\n${certificate}\n EOF`}
      />
    </>
  );
};

export default CertificateDownload;
