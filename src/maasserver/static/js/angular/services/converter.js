/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Converter Service
 *
 * Used by controllers to convert user inputs.
 */

angular.module('MAAS').service('ConverterService', function() {

        // Case is important: 1kB is 1000 bytes, whereas 1KB is 1024 bytes.
        // See https://en.wikipedia.org/wiki/Byte#Unit_symbol
        var UNITS = ['bytes', 'kB', 'MB', 'GB', 'TB'];

        var KILOBYTE = 1000.0;
        var MEGABYTE = 1000.0 * 1000.0;
        var GIGABYTE = 1000.0 * 1000.0 * 1000.0;
        var TERABYTE = 1000.0 * 1000.0 * 1000.0 * 1000.0;

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
                    if(unit === 'bytes') {
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
            if(unit === 'bytes') {
                return Math.floor(data);
            } else if(unit === 'kB') {
                return Math.floor(data * KILOBYTE);
            } else if(unit === 'MB') {
                return Math.floor(data * MEGABYTE);
            } else if(unit === 'GB') {
                return Math.floor(data * GIGABYTE);
            } else if(unit === 'TB') {
                return Math.floor(data * TERABYTE);
            }
        };

        // Convert the data based on unit down to the lowest tolerance to still
        // be the same value in that unit.
        this.roundUnits = function(data, unit) {
            // Support string being passed.
            if(angular.isString(data)) {
                data = parseFloat(data);
            }
            if(unit === 'bytes') {
                return Math.floor(data);
            } else if(unit === 'kB') {
                return Math.floor(data * KILOBYTE) - (0.05 * KILOBYTE);
            } else if(unit === 'MB') {
                return Math.floor(data * MEGABYTE) - (0.05 * MEGABYTE);
            } else if(unit === 'GB') {
                return Math.floor(data * GIGABYTE) - (0.05 * GIGABYTE);
            } else if(unit === 'TB') {
                return Math.floor(data * TERABYTE) - (0.05 * TERABYTE);
            }
        };

        // Round the bytes down to size based on the block size.
        this.roundByBlockSize = function(bytes, block_size) {
            return block_size * Math.floor(bytes / block_size);
        };
    });
