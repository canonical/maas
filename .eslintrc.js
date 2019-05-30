module.exports = {
    "env": {
        "browser": true,
        "es6": true,
        "jasmine": true
    },
    "extends": ["angular", "eslint:recommended"],
    "globals": {
        "__dirname": false,
        "angular": false,
        "Atomics": "readonly",
        "inject": false,
        "setTimeout": false,
        "SharedArrayBuffer": "readonly"
    },
    "parserOptions": {
        "ecmaVersion": 2018,
        "sourceType": "module"
    },
    "rules": {
        "angular/di": [2, "function", { "matchNames": true }],
        "no-unused-vars": [2, { "args": "none" }]
    }
};
