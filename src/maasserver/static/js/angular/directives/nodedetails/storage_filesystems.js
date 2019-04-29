function storageFilesystems() {
  const path = "static/partials/nodedetails/storage/filesystems.html";
  return {
    restrict: "E",
    templateUrl: `${path}?v=${MAAS_config.files_version}`
  };
}

export default storageFilesystems;
