Feature: Settings - Group details

  Scenario: The user can add a group and view its details
    Given the user is logged in
    And the user navigates to the settings groups page
    When the user clicks the "Add group" button
    And the user fills in valid group details
    And the user submits the form
    Then the group creation should succeed
    When the user clicks the created group
    Then the group details page should display the group name