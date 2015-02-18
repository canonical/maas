/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * E2E tests for the login page.
 */

describe("login", function() {

    // Clear all cookies and load the MAAS page before each test. This page
    // does not use angular so we tell protractor to ignore waiting for
    // angular to load.
    beforeEach(function() {
        browser.manage().deleteAllCookies();
        browser.ignoreSynchronization = true;
        browser.get("http://localhost:5253/MAAS/")
    });

    it("has login in title", function() {
        expect(browser.getTitle()).toContain("Login");
    });

    it("has username field", function() {
        expect(element(by.id("id_username")).isPresent()).toBe(true);
    });

    it("has password field", function() {
        expect(element(by.id("id_password")).isPresent()).toBe(true);
    });

    it("has login button", function() {
        expect(
            element(
                by.css('.login input[type="submit"]')).isPresent()).toBe(true);
    });

    it("can login as admin", function() {
        element(by.id("id_username")).sendKeys("admin");
        element(by.id("id_password")).sendKeys("test");
        element(by.css('.login input[type="submit"]')).click();

        expect(
            element.all(
                by.css('#user-link a')).get(0).getText()).toBe("admin");
    });

    it("can login as user", function() {
        element(by.id("id_username")).sendKeys("user");
        element(by.id("id_password")).sendKeys("test");
        element(by.css('.login input[type="submit"]')).click();

        expect(
            element.all(
                by.css('#user-link a')).get(0).getText()).toBe("user");
    });

    it("shows mismatch username and password", function() {
        element(by.id("id_username")).sendKeys("badusername");
        element(by.id("id_password")).sendKeys("badpassword");
        element(by.css('.login input[type="submit"]')).click();

        expect(element(by.css('p.form-errors')).getText()).toBe(
            "Your username and password didn't match. Please try again.");
    });
});
