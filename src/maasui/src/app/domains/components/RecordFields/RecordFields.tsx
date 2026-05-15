import { Col, Row, Select } from "@canonical/react-components";
import { useFormikContext } from "formik";

import FormikField from "@/app/base/components/FormikField";
import { MIN_TTL } from "@/app/store/domain/constants";
import { RecordType } from "@/app/store/domain/types";

export enum Labels {
  Name = "Name",
  Type = "Record type",
  Data = "Data",
  Ttl = "TTL",
}

const recordTypeOptions = [
  { value: "", label: "Type", disabled: true },
  ...Object.values(RecordType).map((value) => {
    return {
      value: value,
      label: value,
    };
  }),
];

const getRecordDataHelp = (type: RecordType) => {
  switch (type) {
    case RecordType.A:
      return "A records require an IPv4 address.";
    case RecordType.AAAA:
      return "AAAA records require an IPv6 address.";
    case RecordType.CNAME:
      return "CNAME records require a canonical domain name.";
    case RecordType.MX:
      return 'MX records require "<preference> <domain name>" of a mail server.';
    case RecordType.NS:
      return "NS records require the domain name of a name server.";
    case RecordType.SRV:
      return 'SRV records require "<priority> <weight> <port> <target>" of a server.';
    case RecordType.SSHPF:
      return 'SSHPF records require "<algorithm> <fptype> <fingerprint>".';
    default:
      return "";
  }
};

const getRecordDataPlaceholder = (type: RecordType) => {
  switch (type) {
    case RecordType.A:
      return "e.g. 192.168.1.1";
    case RecordType.AAAA:
      return "e.g. 001:db8::ff00:42:8329";
    case RecordType.CNAME:
      return "e.g. www.mydomain.com";
    case RecordType.MX:
      return "e.g. 0 mymailserver.example.com";
    case RecordType.NS:
      return "e.g. ns1.domain.com.";
    case RecordType.SRV:
      return "e.g. 0 5 5060 service.example.com";
    case RecordType.SSHPF:
      return "e.g. 2 1 123456789abcdef67890123456789abcdef67890";
    default:
      return "";
  }
};

type Props = {
  editing?: boolean;
};

const RecordFields = ({ editing }: Props): React.ReactElement => {
  const { values } = useFormikContext<{ rrtype: RecordType }>();

  return (
    <Row>
      <Col size={12}>
        <FormikField
          label={Labels.Name}
          name="name"
          placeholder={Labels.Name}
          required
          type="text"
        />
        <FormikField
          component={Select}
          disabled={editing} // when record is edited type can't be changed
          label={Labels.Type}
          name="rrtype"
          options={recordTypeOptions}
          required
        />
        <FormikField
          help={getRecordDataHelp(values.rrtype)}
          label={Labels.Data}
          name="rrdata"
          placeholder={getRecordDataPlaceholder(values.rrtype)}
          required
          type="text"
        />
        <FormikField
          label={Labels.Ttl}
          min={MIN_TTL}
          name="ttl"
          placeholder="TTL in seconds (optional)"
          type="number"
        />
      </Col>
    </Row>
  );
};

export default RecordFields;
