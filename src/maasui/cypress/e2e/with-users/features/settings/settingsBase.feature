Feature: Settings base

  Scenario: The correct heading is rendered
    Given the user is logged in
    When the user navigates to the settings page
    Then the side navigation title should be "Settings"