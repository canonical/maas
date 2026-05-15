Feature: Navigation - non-admin

  Background:
    Given the user is logged in as a non-admin
    And the user navigates to the home page

  Scenario: Clicking the logo navigates to the machines page
    When the user clicks the "Homepage" link in the main navigation
    Then the pathname should equal "/machines"
    And the "Machines" navigation item should be selected
