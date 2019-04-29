/**
 * This should be avoided if at all possible
 * The data should come from the backend
 * There is a launchpad issue for this (LP: #1802307)
 */

function KVMDeployOSBlacklist() {
  return [
    "ubuntu/precise",
    "ubuntu/trusty",
    "ubuntu/xenial",
    "ubuntu/yakkety",
    "ubuntu/zesty",
    "ubuntu/artful"
  ];
}

export default KVMDeployOSBlacklist;
