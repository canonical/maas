Feature: Settings - User add

  Scenario: The user can add a new user
    Given the user is logged in
    And the user navigates to the settings users page
    When the user clicks the "Add user" button
    And the user fills in valid user details
    And the user submits the form
    Then the user creation request should succeed