Feature: Settings - User list

  Scenario: The side nav highlights correctly
    Given the user is logged in
    And the user navigates to the settings users page
    Then the "Users" side navigation item should be active