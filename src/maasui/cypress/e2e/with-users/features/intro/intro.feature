Feature: Intro

  Background:
    Given the user is logged in before the intro is completed
    And the user navigates to the home page

  Scenario: The intro page is displayed after login
    Then the intro page should be displayed

  Scenario: Saving MAAS setup redirects to images setup page
    When the user saves the MAAS setup
    Then the user should be redirected to the images setup page
    When the user clicks the "Select upstream images" button
    And the "Select upstream images to sync" heading is visible
    And the user expands the "Ubuntu" accordion section
    And the user opens the "18.04" release dropdown
    And the user selects and captures the first available option
    And the user clicks the "Save and sync" button

    Then the selected image row should show "Queueing" in the table
    And the "Continue" button should be enabled

  Scenario: The user can skip the initial setup
    When the user skips the initial setup
    Then the user should be redirected to the user setup page
