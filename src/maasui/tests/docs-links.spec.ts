import { test, expect } from "@playwright/test";
import docsUrls from "../src/app/base/docsUrls";

const urls = Object.values(docsUrls);

const redirectErrorMessage = (url: string, location: string | null) => `
  URL NEEDS TO BE UPDATED
  -----------------------------
  FROM:
  ${url}
  
  TO:
  https://maas.io${location}
  
  `;

test.describe("loads the page", () => {
  urls.forEach((url) => {
    test(`${url}`, async () => {
      const docsPage = fetch(url);
      const resCode = await docsPage.then((res) => res.status);
      expect(resCode).toBe(200);
    });
  });
});

test.describe("is a direct link", () => {
  urls.forEach((url) => {
    test(`${url}`, async () => {
      // prevent auto redirect so we can get the HTTP 302 if present
      const docsPage = fetch(url, { redirect: "manual" });
      const { status, headers } = await docsPage.then((res) => res);

      expect(status, redirectErrorMessage(url, headers.get("location"))).toBe(
        200
      );
    });
  });
});
