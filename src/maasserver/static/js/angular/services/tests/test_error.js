/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for ErrorService.
 */

import { makeName } from "testing/utils";
describe("ErrorService", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the ErrorService.
  var ErrorService;
  beforeEach(inject(function($injector) {
    ErrorService = $injector.get("ErrorService");
  }));

  it("initializes _error to null", function() {
    expect(ErrorService._error).toBeNull();
  });

  describe("raiseError", function() {
    it("sets _error", function() {
      var error = makeName("error");
      ErrorService.raiseError(error);
      expect(ErrorService._error).toBe(error);
    });

    it("only sets _error once", function() {
      var errors = [makeName("error"), makeName("error")];
      ErrorService.raiseError(errors[0]);
      ErrorService.raiseError(errors[1]);
      expect(ErrorService._error).toBe(errors[0]);
    });
  });
});
