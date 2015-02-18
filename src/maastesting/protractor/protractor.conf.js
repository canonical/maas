// Protractor configuration

exports.config = {

  // use the jasmine framework for tests
  framework: 'jasmine',

  // connect to webdriver default address
  seleniumAddress: 'http://localhost:4444',

  // list of files to run
  specs: [
    'tests/*.js',
  ]
}
