@machine-list
Feature: Machine listing

  Background:
    Given the user is logged in
    And the user navigates to the machines page

  Scenario: The correct heading is rendered
    Then the machine list heading should be visible

  Scenario Outline: Machines can be grouped by all supported keys
    Given all options of grouping are available
    When the user selects "<group by>" from the group by dropdown
    Then the machines grid for "<group by>" should exist

    Examples:
      | group by                |
      | No grouping             |
      | Group by status         |
      | Group by owner          |
      | Group by resource pool  |
      | Group by architecture   |
      | Group by domain         |
      | Group by parent         |
      | Group by KVM            |
      | Group by KVM type       |
      | Group by power state    |
      | Group by zone           |

  Scenario: Displays machine counts with active filters
    Given there are commissioning machines matching a generated hostname
    When the user groups machines by status
    And the user filters machines by the generated hostname and commissioning status
    Then the text "Showing 2 out of 2 machines" should be visible
    When the user selects the commissioning group
    And the user deletes the selected machines
    Then the delete 2 machines confirmation should be handled successfully

  Scenario: Replaces the URL when selecting filters
    Given the user has visited the network discovery page
    And the user navigates to the machines page
    And initial state of the page is correct
    When the user clicks the button matching "filters"
    And the user selects the "Status" filter tab
    And the user enables the "Testing" filter
    Then the machine searchbox should contain "status:(=testing)"
    And the machine URL should contain the testing status filter
    When the user navigates back
    Then the user should be on the network discovery page
    When the user navigates forward
    Then the machine searchbox should contain "status:(=testing)"
    And the machine URL should contain the testing status filter

  Scenario: Can load filters from the URL
    Given the user opens the machines page with the "new" status filter in the URL
    Then the machine searchbox should contain "status:(=new)"

  Scenario: Can hide machine table columns
    Given the viewport is "macbook-15"
    Then the machine table should show 11 columns
    When the user clicks the "Columns" button
    And the user hides the "Status" column
    Then the machine table should show 10 columns
    And the "Status" header should not exist
    When the user refreshes the page
    Then the machine table should show 10 columns
    And the "Status" header should not exist
    When the viewport is "samsung-s10"
    Then the machine table should show 3 columns
    When the viewport is "macbook-15"
    Then the machine table should show 11 columns

  Scenario: Can select a machine range
    Given three generated machines exist
    And the user disables grouping
    And the user filters by the generated machine prefix
    Then the text "Showing 3 out of 3 machines" should be visible
    When the user selects the first machine
    And the user shift-selects the third machine
    Then the second machine should be selected
    When the user deletes the selected machines
    Then the text matching "No machines match the search criteria." should exist

  Scenario: Can filter machine list by deployment target
    Given a pools link should be visible
    And the "0 pools" link should not be visible
    When the user clicks the button matching "filters"
    And the user selects the "Deployment target" filter tab
    Then the "deployed to disk" filter should be visible
    When the user enables the filter matching "Deployed in memory"
    Then the machine searchbox should contain "deployment_target:(=memory)"