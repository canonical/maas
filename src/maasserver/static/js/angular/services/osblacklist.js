/**
 * This should be avoided if at all possible
 * The data should come from the backend
 * There is a launchpad issue for this (LP: #1802307)
 */
angular.module('MAAS').service('KVMDeployOSBlacklist', function() {
  return [
    'ubuntu/precise',
    'ubuntu/trusty',
    'ubuntu/xenial',
    'ubuntu/yakkety',
    'ubuntu/zesty',
    'ubuntu/artful'
  ];
});
