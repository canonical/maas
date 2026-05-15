Feature: Settings general configuration

  Background:
    Given the user is logged in
    And the user navigates to the settings general page

  Scenario: Cancel restores the initial notification checkbox value
    Then the "Enable new release notifications" checkbox should be checked
    When the user toggles the "Enable new release notifications" checkbox
    Then the "Enable new release notifications" checkbox should not be checked
    When the user clicks the "Cancel" button
    Then the "Enable new release notifications" checkbox should be checked