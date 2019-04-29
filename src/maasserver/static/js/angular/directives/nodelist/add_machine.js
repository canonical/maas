function addMachine() {
  const path = "static/partials/nodelist/add-machine.html";
  return {
    restrict: "E",
    scope: true,
    templateUrl: `${path}?v=${MAAS_config.files_version}`
  };
}

export default addMachine;
