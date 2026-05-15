import { splitCertificateName } from "./certificates";

describe("splitCertificateName", () => {
  it("handles null case", () => {
    expect(splitCertificateName(null)).toStrictEqual(null);
  });

  it("handles missing host", () => {
    expect(splitCertificateName("bad-cert")).toStrictEqual({
      host: "",
      name: "bad-cert",
    });
  });

  it("can split a certificate name into name and host", () => {
    expect(splitCertificateName("machine@host")).toStrictEqual({
      host: "host",
      name: "machine",
    });
    expect(splitCertificateName("machine@address@host")).toStrictEqual({
      host: "host",
      name: "machine@address",
    });
  });
});
