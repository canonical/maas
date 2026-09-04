// CSP-safe Swagger UI bootstrap shared by V2 and V3 API docs.
// Reads OpenAPI URL from data-openapi-url attribute to support both APIs.
(function () {
  var currentScript = document.currentScript;
  var openapiUrl =
    (currentScript && currentScript.dataset && currentScript.dataset.openapiUrl) ||
    "/openapi.json";

  window.addEventListener("load", function () {
    window.ui = SwaggerUIBundle({
      url: openapiUrl,
      dom_id: "#swagger-ui",
      deepLinking: true,
      presets: [SwaggerUIBundle.presets.apis],
    });
  });
})();
