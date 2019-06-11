const config = {
  moduleDirectories: [
    '<rootDir>/src/maasserver/static/js/angular/',
    'node_modules'
  ],
  moduleNameMapper: {
    '.scss$': '<rootDir>/src/maasserver/static/js/angular/testing/proxy-module.js'
  },
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
    '<rootDir>/src/maasserver/static/js/angular/*/tests/test_*.js'
  ],
  testURL: 'http://example.com:8000/',
  transform: {
    '^.+\\.js$': 'babel-jest',
    '^.+\\.html?$': 'html-loader-jest'
  },
};

module.exports = config;
