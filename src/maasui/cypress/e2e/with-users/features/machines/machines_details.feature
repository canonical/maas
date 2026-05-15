Feature: Machine details

Background:
    Given the user is logged in
    And the user navigates to the machines page

Scenario: The subnet column is hidden on small screens
    Given the user creates a machine through the add machine flow
    And the user searches for the created machine    
    When the user opens the created machine details
    And the user clicks the "Network" link
    Then the ip column header should exist
    And the subnet column header should exist
    When the user switches to an ipad mini landscape viewport
    Then the ip column header should exist
    And the "subnet" column header should not exist
    When the user deletes the current machine
    Then the user should be redirected to the machines page


Scenario: The machine commissioning details are displayed
    Given the user creates a machine through the add machine flow
    And the user searches for the created machine
    When the user opens the created machine details
    And the user opens the machine actions menu
    And the user aborts commissioning
    And the user opens the "Scripts" tab
    And the user opens the first commissioning details row
    Then the sub-heading matching "details" text should exist
    When the user deletes the machine
    Then the user should be redirected to the machines page