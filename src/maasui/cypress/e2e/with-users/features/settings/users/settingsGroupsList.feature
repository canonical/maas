Feature: Settings - Groups list

  Scenario: The side nav highlights correctly
    Given the user is logged in
    And the user navigates to the settings groups page
    Then the "Groups" side navigation item should be active

  Scenario: The groups list page renders with expected elements
    Given the user is logged in
    And the user navigates to the settings groups page
    Then the "Groups" heading should exist
    And the groups list has an "Add group" button