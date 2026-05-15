Feature: Images sync

  Background:
    Given the user is logged in
    And the user navigates to the images page
    And the page is loaded

  Scenario: The user can add a synced image
    When the user clicks the "Select upstream images" button
    And the "Select upstream images to sync" heading is visible
    And the user expands the "Ubuntu" accordion section
    And the user opens the "22.04" release dropdown
    And the user selects and captures the first available option
    And the user clicks the "Save and sync" button
    Then the selected image row should show "Queueing" in the table
