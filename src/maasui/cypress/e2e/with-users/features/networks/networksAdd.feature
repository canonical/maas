Feature: Subnets - Add

Background:
    Given the user is logged in 
    And the user navigates to the networks page
    And the "Subnets by fabric" table has loaded

Scenario: The user can add a new subnet
    When the user creates a new fabric
    And the user creates a new space
    And the user creates a new VLAN
    And the user creates a new subnet
    Then the subnet appears under the correct fabric

Scenario: The user can delete a created subnet
    When the user deletes the created subnet
    Then fabric list should not include deleted subnet

Scenario: An error is displayed when trying to add a VLAN with a VID that already exists
    When the user tries to add a VLAN with a VID that already exists
    Then the text matching "A VLAN with the specified VID already exists in the destination fabric." should exist

Scenario: An error is displayed when trying to add a Fabric with a name that already exists
    When the user tries to add a Fabric with a name that already exists
    Then text "this name already exists" should be visible

Scenario: An error is displayed when trying to add a Space with a name that already exists
    When the user tries to add a Space with a name that already exists
    Then text "this name already exists" should be visible