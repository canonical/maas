Feature: Zones

  Scenario: The correct heading is rendered
    Given the user is logged in
    When the user navigates to the zones page
    Then the main toolbar heading should be "Availability zones"