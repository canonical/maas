/* eslint-disable @typescript-eslint/no-require-imports */
const { constructURL } = require("../utils");

const TIMEOUT = 120000;

const waitForMachines = async (context, commands, pageSize = 50) => {
  context.log.info("waiting for machine list count");
  await commands.wait.byCondition(
    `document.querySelector('[data-testid="main-toolbar-heading"]').textContent.includes("1000 machines")`,
    TIMEOUT
  );
  context.log.info(`waiting for ${pageSize} machine list rows`);
  await commands.wait.byCondition(
    `document.querySelectorAll('table[aria-label] tbody tr.machine-list__machine')?.length === ${pageSize}`,
    TIMEOUT
  );
};

const coldCache = async (context, commands) => {
  await commands.cache.clearKeepCookies();
  await commands.measure.start("Machine list - cold cache");
  await commands.navigate(constructURL(context, "/machines"));
  await waitForMachines(context, commands);
  return commands.measure.stop();
};

const warmCache = async (context, commands) => {
  await commands.navigate(constructURL(context, "/machines"));
  await commands.measure.start("Machine list - warm cache");
  await commands.navigate(constructURL(context, "/machines"));
  await waitForMachines(context, commands);
  return commands.measure.stop();
};

const customPageSize = async (context, commands, pageSize) => {
  // set group by to none
  await commands.js.run(`window.localStorage.setItem("grouping", '""')`);
  // set custom machine list page size
  await commands.js.run(
    `window.localStorage.setItem("machineListPageSize", ${pageSize})`
  );
  await commands.measure.start(`Machine list - ${pageSize} per page`);
  await commands.navigate(constructURL(context, "/machines"));
  await waitForMachines(context, commands, pageSize);
  return commands.measure.stop();
};

module.exports = async (context, commands) => {
  await coldCache(context, commands);
  await warmCache(context, commands);
  await customPageSize(context, commands, 10);
  await customPageSize(context, commands, 20);
  await customPageSize(context, commands, 50);
  await customPageSize(context, commands, 100);
  return customPageSize(context, commands, 200);
};
