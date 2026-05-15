Feature: Side panel

  Background:
    Given the user is logged in
    And the user expands the main navigation
    And the user navigates to the devices page
    And the user clicks the "Add device" button

  Scenario: Side panel closes if ESC key is pressed
    Given the side panel is visible
    And the "Add device" panel is visible
    When the user presses the "esc" key
    Then the "Add device" panel should not exist
    And the side panel should not be visible

  Scenario: Side panel closes when navigating to a different page
    Given the side panel is visible
    And the "Add device" panel is visible
    When the user navigates to the machines page
    Then the side panel should not be visible
