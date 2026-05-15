Feature: Pools list

  Scenario: The correct heading is rendered
    Given the user is logged in
    When the user navigates to the pools page
    Then the heading matching "[0-9]+ machine[s]? in [0-9]+ pool[s]?" text should exist