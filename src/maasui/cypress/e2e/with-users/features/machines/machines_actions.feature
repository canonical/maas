@machine-actions

Feature: Machine listing - actions

  Background:
    Given the user is logged in
    And the user navigates to the machines page
    And the machines table is loaded

  Scenario: Displays the correct actions in the action menu
    When the user selects the first machine in the grid
    Then the following action groups should be available:
      | group         | actions                                                     |
      | Actions       | Commission, Allocate, Deploy, Release, Abort, Clone from   |
      | Power         | Power on, Power off, Soft power off                         |
      | Troubleshoot  | Test, Enter rescue mode, Exit rescue mode, Mark fixed, Mark broken, Override failed testing |
      | Categorise    | Tag, Set zone, Set pool                                     |
      | Lock          | Lock, Unlock                                                |
    And the "Delete" action should be enabled

  Scenario Outline: Loads machine action form
    When the user selects the first machine in the grid
    And the user opens the "<action>" form from the "<group>" menu
    Then the "<action>" side panel should be visible
    When the user cancels the "<action>" form
    Then the "<action>" side panel should not exist

    Examples:
      | group         | action                  |
      | Actions       | Commission              |
      | Actions       | Allocate                |
      | Actions       | Deploy                  |
      | Actions       | Release                 |
      | Actions       | Abort                   |
      | Actions       | Clone from              |
      | Power         | Power on                |
      | Power         | Power off               |
      | Power         | Soft power off          |
      | Troubleshoot  | Test                    |
      | Troubleshoot  | Enter rescue mode       |
      | Troubleshoot  | Exit rescue mode        |
      | Troubleshoot  | Mark fixed              |
      | Troubleshoot  | Mark broken             |
      | Troubleshoot  | Override failed testing |
      | Categorise    | Tag                     |
      | Categorise    | Set zone                |
      | Categorise    | Set pool                |
      | Lock          | Lock                    |
      | Lock          | Unlock                  |

  Scenario: Loads machine Delete form
    When the user selects the first machine in the grid
    And the user clicks the button matching "Delete"
    Then the "Delete" side panel should be visible
    When the user cancels the "Delete" form
    Then the "Delete" side panel should not exist

  Scenario: Can create and set the pool of a machine
    Given the user filters the machine list by the generated machine
    And the user selects that machine
    When the user opens the "Set pool" form from the "Categorise" menu
    And the user creates a new pool
    And the user clicks the button matching "Set pool for machine"
    Then the "Set pool" side panel should not exist
    And the new pool name should be visible in the machines grid

  Scenario: Can create and add a tag to a machine
    Given the user filters the machine list by the generated machine
    And the user selects that machine
    When the user opens the "Tag" form from the "Categorise" menu
    And the user creates a new tag
    Then the "Tag changes" table should contain the new tag marked "To be added"
    When the user clicks the button matching "Save"
    Then the new tag should be visible in the machines grid

  Scenario: Can open a soft power off form
    When the user selects the first machine in the grid
    And the user opens the "Soft power off" form from the "Power" menu
    Then the "Soft power off" side panel should be visible
    And the heading matching "Soft power off" text should exist
    And the text matching "a soft power off generally asks the os to shutdown the system gracefully before powering off\. it is only supported by ipmi." should exist