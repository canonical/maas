function storageDisksPartitions() {
  const path = "static/partials/nodedetails/storage/disks-partitions.html";
  return {
    restrict: "E",
    templateUrl: `${path}?v=${MAAS_config.files_version}`
  };
}

export default storageDisksPartitions;
