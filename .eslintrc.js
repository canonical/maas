module.exports = {
    "env": {
        "browser": true,
        "es6": true
    },
    "extends": ["eslint:recommended"],
    "globals": {
        "__dirname": false,
        "$": false,
        "afterEach": false,
        "angular": false,
        "Atomics": "readonly",
        "beforeEach": false,
        "describe": false,
        "expect": false,
        "inject": false,
        "it": false,
        "jasmine": false,
        "jest": false,
        "MAAS_config": false,
        "module": false,
        "require": false,
        "setTimeout": false,
        "SharedArrayBuffer": "readonly",
        "spyOn": false
    },
    "parserOptions": {
        "ecmaVersion": 2018,
        "sourceType": "module"
    },
    "rules": {
        "no-unused-vars": [2, { "args": "none" }]
    }
};
