module.exports = {
    "env": {
        "browser": true,
        "es6": true,
        "jasmine": true
    },
    "extends": ["eslint:recommended"],
    "globals": {
        "__dirname": false,
        "$": false,
        "angular": false,
        "Atomics": "readonly",
        "inject": false,
        "jest": false,
        "MAAS_config": false,
        "require": false,
        "setTimeout": false,
        "SharedArrayBuffer": "readonly"
    },
    "parserOptions": {
        "ecmaVersion": 2018,
        "sourceType": "module"
    },
    "rules": {
        "no-unused-vars": [2, { "args": "none" }]
    }
};
