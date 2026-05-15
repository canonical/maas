Feature: Settings security session timeout

  Scenario: Changing the refresh token expiration logs the user out
    Given the user is logged in
    And the user navigates to the settings token expiration page
    When the user clears the "Refresh token expiration" field
    And the user enters new value into the refresh token expiration field
    And the user saves the token expiration settings if possible
    Then the login form should be displayed