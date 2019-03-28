module.exports = {
    "env": {
        "browser": true,
        "es6": true,
        "jasmine": true
    },
    "extends": ["angular", "eslint:recommended"],
    "globals": {
        "Atomics": "readonly",
        "SharedArrayBuffer": "readonly",
        "angular": false,
        "module": false,
        "inject": false,
        "makeName": false, // TODO: export as named function
        "makeInteger": false, // TODO: export as named function
        "makeFakeResponse": false // TODO: export as named function
    },
    "parserOptions": {
        "ecmaVersion": 2018
    },
    "rules": {
        "angular/di": [2, "function", { "matchNames": true }]
    }
};
