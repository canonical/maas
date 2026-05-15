Feature: Static Routes

Background:
    Given the user is logged in 
    And the user navigates to the networks by fabric page
    And the viewport is "macbook-11"

Scenario: The user can add, edit and delete a static route
    When the user opens the first subnet
    And the user navigates to static routes
    And the user adds a static route
    And the user edits the static route
    And the user deletes the static route
    Then the static route should not exist