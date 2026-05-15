Feature: DNS

  Scenario: The correct heading is rendered
    Given the user is logged in
    When the user navigates to the domains page
    Then the main toolbar heading should be "DNS"