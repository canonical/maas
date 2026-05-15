Feature: Network Discovery

  Scenario: The correct heading is rendered
    Given the user is logged in
    When the user navigates to the network discovery page
    Then the main toolbar heading should be "Network discovery"