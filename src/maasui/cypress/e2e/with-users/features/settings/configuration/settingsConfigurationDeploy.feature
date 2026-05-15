Feature: Settings deploy configuration

  Scenario: The deploy configuration page displays a correct default value for hardware sync interval
    Given the user is logged in
    And the user navigates to the settings deploy page
    Then the deploy configuration form should be displayed
    And the "Default hardware sync interval" field should have the value "15"
