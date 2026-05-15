Feature: Navigation - admin - collapse

Background:
    Given the user is logged in
    And the viewport is "macbook-13"
    And the user navigates to the home page

Scenario: Keyboard shortcut can expand and collapse the side navigation
    Given the viewport is "ipad-mini"
    And the page is loaded
    And the navigation is collapsed
    When the user presses "[" key
    Then the navigation is expanded
    When the user presses "[" key
    Then the navigation is collapsed

Scenario: Keyboard shortcut is ignored when modifier key is pressed
    Given the viewport is "ipad-mini"
    And the page is loaded
    And the navigation is collapsed
    When the user presses "{ctrl}[" key
    Then the navigation is collapsed

Scenario: Clicking a button expands and collapses the side navigation
    Given the viewport is "ipad-mini"
    And the page is loaded
    And the navigation is collapsed
    When the user clicks the "expand main navigation" button
    Then the navigation is expanded
    When the user clicks the "collapse main navigation" button
    Then the navigation is collapsed


Scenario: Opening and closing the menu on mobile
    Given the viewport is "iphone-8"
    And the main navigation should not be visible 
    When the user clicks the "Menu" button in the navigation banner
    Then the main navigation should be visible
    When the user clicks the "close menu" button in the main navigation 
    Then the main navigation should not be visible 

Scenario: Clicking a link automatically closes the menu on mobile
    Given the viewport is "iphone-8"
    And the main navigation should not be visible
    When the user clicks the "Menu" button in the navigation banner
    And the user clicks the "devices" link in the main navigation
    Then the main navigation should not be visible