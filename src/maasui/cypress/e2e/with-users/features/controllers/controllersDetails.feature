Feature: Controllers details

Background: 
    Given the user is logged in
    And the user navigates to the controllers page
    And the user navigates to details page of the first controller
    And the text matching "Summary" should exist

Scenario: The user can add a tag to the controller
    When the user adds a tag to the controller
    And the user clicks the created tag
    Then the correct tag is displayed in the searchbox
    And the correct number of controllers is displayed

Scenario: Valid actions on the controller details page are listed
    When the user clicks the "Take action" button
    Then the "Set zone" action should exist
    And the "Delete" action should exist
    And the "Deploy" action should not exist

Scenario: Displaying controller commissioning details
    When the user clicks the "Commissioning" link
    And the user clicks name of the first script
    Then the heading matching "details" text should exist