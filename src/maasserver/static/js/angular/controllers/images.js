/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Images Controller
 */

angular.module('MAAS').controller('ImagesController', [
    '$rootScope', function($rootScope) {
        $rootScope.page = "images";
        $rootScope.title = "Boot Images";
    }]);
