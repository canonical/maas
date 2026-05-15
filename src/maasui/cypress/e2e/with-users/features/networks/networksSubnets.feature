Feature: Subnets

Background: 
    Given the user is logged in 
    And the user navigates to the subnets page
    And the viewport is "macbook-11"

Scenario: The correct heading is rendered
    Then the heading should be "Networks"

Scenario: The main networking view is being displayed correctly
    Then correct headers exist

Scenario: If no group parameter has been set then the URL gets updated to default grouping
    Given the user navigates to the networks page 
    And no group parameter has been set
    Then the URL gets updated to default grouping

Scenario: Subnets are by default grouped by fabric
    Then subnets are by default grouped by fabric

Scenario: Grouping by space is allowed
    When the user selects grouping by space
    Then subnets are grouped by space