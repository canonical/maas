const config = {
  moduleDirectories: [
    '<rootDir>/src/maasserver/static/js/angular/',
    'node_modules'
  ],
  setupFiles: [
    '<rootDir>/src/maasserver/static/js/angular/testing/setup-jest.js',
  ],
  setupFilesAfterEnv: [
    '/usr/share/javascript/angular.js/angular.js',
    '/usr/share/javascript/angular.js/angular-route.js',
    '/usr/share/javascript/angular.js/angular-mocks.js',
    '/usr/share/javascript/angular.js/angular-cookies.js',
    '/usr/share/javascript/angular.js/angular-sanitize.js',
    '<rootDir>/src/maasserver/static/js/angular/3rdparty/ng-tags-input.js',
    '<rootDir>/src/maasserver/static/js/angular/3rdparty/vs-repeat.js',
    '<rootDir>/src/maasserver/static/js/angular/entry.js',
    '<rootDir>/src/maasserver/static/js/angular/testing/setup.js',

  ],
  snapshotSerializers: ['enzyme-to-json/serializer'],
  testMatch: [
    // Disable the test catch-all until the switch to Jest is made.
    // '<rootDir>/src/maasserver/static/js/angular/*/tests/test_*.js',
    '<rootDir>/src/maasserver/static/js/angular/controllers/tests/test_dashboard.js',
  ],
  transform: {
    '^.+\\.js$': 'babel-jest',
  },
};

module.exports = config;
