/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Converter Service
 *
 * Used by controllers to convert user inputs.
 */

angular.module('MAAS').service('ConverterService', function() {

        var UNITS = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        var KB = 1000.0;
        var MB = 1000.0 * 1000.0;
        var GB = 1000.0 * 1000.0 * 1000.0;
        var TB = 1000.0 * 1000.0 * 1000.0 * 1000.0;

        // Convert the bytes to a unit.
        this.bytesToUnits = function(bytes) {
            // Support string being passed.
            if(angular.isString(bytes)) {
                bytes = parseInt(bytes, 10);
            }

            var i, unit, converted = bytes;
            for(i = 0; i < UNITS.length; i++) {
                unit = UNITS[i];
                if(Math.abs(converted) < 1000.0 || unit === 'TB') {
                    var string = converted.toFixed(1) + " " + unit;
                    if(unit === 'Bytes') {
                        string = converted + " " + unit;
                    }
                    return {
                        original: bytes,
                        converted: converted,
                        units: unit,
                        string: string
                    };
                }
                converted /= 1000.0;
            }
        };

        // Convert the data based on the unit to bytes.
        this.unitsToBytes = function(data, unit) {
            // Support string being passed.
            if(angular.isString(data)) {
                data = parseFloat(data);
            }
            if(unit === 'Bytes') {
                return Math.floor(data);
            } else if(unit === 'KB') {
                return Math.floor(data * KB);
            } else if(unit === 'MB') {
                return Math.floor(data * MB);
            } else if(unit === 'GB') {
                return Math.floor(data * GB);
            } else if(unit === 'TB') {
                return Math.floor(data * TB);
            }
        };

        // Convert the data based on unit down to the lowest tolerance to still
        // be the same value in that unit.
        this.roundUnits = function(data, unit) {
            // Support string being passed.
            if(angular.isString(data)) {
                data = parseFloat(data);
            }
            if(unit === 'Bytes') {
                return Math.floor(data);
            } else if(unit === 'KB') {
                return Math.floor(data * KB) - (0.05 * KB);
            } else if(unit === 'MB') {
                return Math.floor(data * MB) - (0.05 * MB);
            } else if(unit === 'GB') {
                return Math.floor(data * GB) - (0.05 * GB);
            } else if(unit === 'TB') {
                return Math.floor(data * TB) - (0.05 * TB);
            }
        };

        // Round the bytes down to size based on the block size.
        this.roundByBlockSize = function(bytes, block_size) {
            return block_size * Math.floor(bytes / block_size);
        };
    });
