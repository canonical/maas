const constructURL = (context, path) =>
  `http://${context.options.domain}:${context.options.port}/MAAS/r${path}`;

module.exports = {
  constructURL,
};
