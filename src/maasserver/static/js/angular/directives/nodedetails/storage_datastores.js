function storageDatastores() {
  const path = "static/partials/nodedetails/storage/datastores.html";
  return {
    restrict: "E",
    templateUrl: `${path}?v=${MAAS_config.files_version}`
  };
}

export default storageDatastores;
