Feature: Machine add

  Background:
    Given the user is logged in
    And the user navigates to the machines page
    And the user opens the add machine form

  Scenario: The user can add a machine
    When the user fills in valid machine details
    And the user submits the form
    Then the side panel should not be visible

  Scenario: ESC key press closes the add machine form
    Given the "Add machine" heading is visible
    When the user presses the "esc" key
    Then the "Add machine" header should not exist
