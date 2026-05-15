import breakLines from "./breakLines";

describe("breakLines", () => {
  it("handles null text value", () => {
    expect(breakLines(null, true, 15)).toBe("");
  });

  it("handles lines that are the exact expected length", () => {
    expect(
      breakLines("Lorem ipsum dolor sit amet, consectetur adipiscinges")
    ).toBe("Lorem ipsum dolor sit amet, consectetur adipiscinges");
  });

  it("handles lines with trailing whitespace", () => {
    expect(
      breakLines("Lorem ipsum dolor sit amet, consectetur adipiscinges ")
    ).toBe("Lorem ipsum dolor sit amet, consectetur adipiscinges");
  });

  it("breaks words at the desired length", () => {
    expect(
      breakLines(
        "Lorem ipsum dolor sit amet, consectetur adipiscinges lit. Nam dapibus"
      )
    ).toBe(
      "Lorem ipsum dolor sit amet, consectetur adipiscinges \nlit. Nam dapibus"
    );
  });

  it("handles extra whitespace at the line break", () => {
    expect(
      breakLines(
        "Lorem ipsum dolor sit amet, consectetur adipiscinges   lit. Nam dapibus"
      )
    ).toBe(
      "Lorem ipsum dolor sit amet, consectetur adipiscinges \nlit. Nam dapibus"
    );
  });

  it("breaks at the previous word break for longer lines", () => {
    expect(
      breakLines(
        "Lorem ipsum dolor sit amet, consectetur adipiscingeslit. Nam dapibus"
      )
    ).toBe(
      "Lorem ipsum dolor sit amet, consectetur \nadipiscingeslit. Nam dapibus"
    );
  });

  it("handles no whitespace", () => {
    expect(
      breakLines(
        "LoremipsumdolorsitametconsecteturadipiscingeslitNamdapibustellusvitaevenenatisfacilesisis"
      )
    ).toBe(
      "LoremipsumdolorsitametconsecteturadipiscingeslitNamd \napibustellusvitaevenenatisfacilesisis"
    );
  });

  it("handles no whitespace within the line limit", () => {
    expect(
      breakLines(
        "LoremipsumdolorsitametconsecteturadipiscingeslitNamdapibustellusvita evenenatisfacilesisis"
      )
    ).toBe(
      "LoremipsumdolorsitametconsecteturadipiscingeslitNamd \napibustellusvita evenenatisfacilesisis"
    );
  });

  it("handles breaking mid word", () => {
    expect(
      breakLines(
        "LoremipsumdolorsitametconsecteturadipiscingeslitNamdapibustellusvitaevenenatisfacilesisis",
        false
      )
    ).toBe(
      "LoremipsumdolorsitametconsecteturadipiscingeslitNamd \napibustellusvitaevenenatisfacilesisis"
    );
  });

  it("handles whitespace at the breakpoint", () => {
    expect(
      breakLines(
        "LoremipsumdolorsitametconsecteturadipiscingeslitNamd apibustellusvitaevenenatisfacilesisis",
        false
      )
    ).toBe(
      "LoremipsumdolorsitametconsecteturadipiscingeslitNamd \napibustellusvitaevenenatisfacilesisis"
    );
  });

  it("can break at a provided length", () => {
    expect(breakLines("Lorem ipsum dolor sit amet", true, 15)).toBe(
      "Lorem ipsum \ndolor sit amet"
    );
  });
});
