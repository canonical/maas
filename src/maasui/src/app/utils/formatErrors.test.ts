import { formatErrors } from "./formatErrors";

describe("formatErrors", () => {
  it("does not format a single string", () => {
    const error = "Error message";
    expect(formatErrors(error)).toEqual("Error message");
  });

  it("correctly formats an array of error strings", () => {
    const error = ["Error 1.", "Error 2."];
    expect(formatErrors(error)).toEqual("Error 1. Error 2.");
  });

  it("correctly formats an error object", () => {
    const error = {
      name: "Too long.",
      date: "Too late.",
    };
    expect(formatErrors(error)).toEqual("name: Too long. date: Too late.");
  });

  it("correctly formats an error object containing arrays", () => {
    const error = {
      name: ["Too long.", "Too late."],
    };
    expect(formatErrors(error)).toEqual("name: Too long. Too late.");
  });

  it("can return the errors for a single key", () => {
    const error = {
      name: "Too long.",
      date: "Too late.",
    };
    expect(formatErrors(error, "name")).toEqual("Too long.");
  });

  it("correctly formats fetch TypeError", () => {
    const typeError = new TypeError("Failed to fetch");
    expect(formatErrors(typeError)).toEqual("Failed to fetch");
  });

  it("correctly formats a generic Error", () => {
    const error = new Error("Something went wrong.");
    expect(formatErrors(error)).toEqual("Something went wrong.");
  });

  it("correctly formats a JSON string error", () => {
    const jsonError =
      '{"__all__": ["The primary rack controller must be up and running to set a secondary rack controller."]}';
    expect(formatErrors(jsonError)).toEqual(
      "The primary rack controller must be up and running to set a secondary rack controller."
    );
  });

  it("can handle HTML", () => {
    const html = `
    <html>
      <head>
        <title>502 Bad Gateway</title>
      </head>
      <body>
        <center>
          <h1>502 Bad Gateway</h1>
        </center>
        <hr>
        <center>nginx/1.18.0 (Ubuntu)</center>
      </body>
    </html>
    `;

    expect(formatErrors(html)).toEqual("502 Bad Gateway nginx/1.18.0 (Ubuntu)");
  });
});
