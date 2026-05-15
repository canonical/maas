// eslint-disable-next-line @typescript-eslint/no-require-imports
const { constructURL } = require("./utils");

const TIMEOUT = 5000;

module.exports = async function (context, commands) {
  await commands.cdp.send("Network.setCookie", {
    domain: context.options.domain,
    name: "skipsetupintro",
    value: "true",
  });
  await commands.cdp.send("Network.setCookie", {
    domain: context.options.domain,
    name: "skipintro",
    value: "true",
  });
  await commands.navigate(constructURL(context, "/"));
  await commands.wait.bySelector("input[name='username']", TIMEOUT);
  await commands.addText.byName("admin", "username");
  await commands.click.bySelector("button.p-button--positive");
  await commands.wait.bySelector(
    "input[name='password']:not([hidden])",
    TIMEOUT
  );
  await commands.addText.byName("test", "password");
  // Wait for the login button to be enabled before clicking it
  await commands.wait.byCondition(
    `document.querySelector("button.p-button--positive")?.textContent?.trim() === "Login"`,
    TIMEOUT
  );
  await commands.click.bySelector("button.p-button--positive");
  await commands.wait.bySelector(
    "[data-testid='section-header-title-spinner']",
    TIMEOUT
  );
  await commands.wait.byXpath("//a//span[text()='admin']", TIMEOUT);
};
