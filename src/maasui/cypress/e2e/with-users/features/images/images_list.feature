Feature: Images list

  Scenario: The correct heading is rendered
    Given the user is logged in
    When the user navigates to the images page
    Then the main toolbar heading should be "Images"