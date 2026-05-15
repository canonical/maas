import express from "express";
import fs from "fs";
import https from "https";
import { createProxyMiddleware } from "http-proxy-middleware";
import { config } from "dotenv-flow";

config();

const BASENAME = process.env.BASENAME;
const VITE_BASENAME = process.env.VITE_BASENAME;

var app = express();

const PROXY_PORT = process.env.PROXY_PORT || 8400;
const VITE_PORT = 8401;

app.get(BASENAME, (req, res) => res.redirect(`${BASENAME}${VITE_BASENAME}`));
app.get("/", (req, res) => res.redirect(`${BASENAME}${VITE_BASENAME}`));
app.get(`${BASENAME}/`, (req, res) =>
  res.redirect(`${BASENAME}${VITE_BASENAME}`)
);

const DOCS = `${BASENAME}/docs`;
const API_ENDPOINTS = [
  `${BASENAME}/api`,
  `${BASENAME}/accounts`,
  `${BASENAME}/a`,
];
const MAAS_ENDPOINTS = [DOCS, ...API_ENDPOINTS];

// Proxy docs and API endpoints to the MAAS.
app.use(
  createProxyMiddleware(MAAS_ENDPOINTS, {
    changeOrigin: true,
    onProxyReq(proxyReq) {
      // Django's CSRF protection requires requests to come from the correct
      // protocol, so this makes XHR requests work when using TLS certs.
      proxyReq.setHeader(
        "Origin",
        `${process.env.MAAS_URL.replace(/\/$/, "")}`
      );
      proxyReq.setHeader("Referer", `${process.env.MAAS_URL}${proxyReq.path}`);
    },
    secure: false,
    target: process.env.MAAS_URL,
  })
);

// Proxy the WebSocket API endpoint to the MAAS.
app.use(
  createProxyMiddleware(`${BASENAME}/ws`, {
    secure: false,
    target: process.env.MAAS_URL,
    ws: true,
  })
);

// Proxy the HMR endpoint to the React client.
app.use(
  createProxyMiddleware("/sockjs-node", {
    target: `http://localhost:${VITE_PORT}/`,
    ws: true,
  })
);

// Proxy to the React client.
if (process.env.STATIC_DEMO !== "true") {
  app.use(
    createProxyMiddleware("/", {
      target: `http://localhost:${VITE_PORT}/`,
    })
  );
}

if (process.env.STATIC_DEMO === "true") {
  app.use(`${BASENAME}${VITE_BASENAME}`, express.static("./build"));
  app.use(`*`, express.static("./build"));
}

if (process.env.HTTPS_CERT && process.env.HTTPS_KEY) {
  const options = {
    cert: fs.readFileSync(process.env.HTTPS_CERT),
    key: fs.readFileSync(process.env.HTTPS_KEY),
  };
  https.createServer(options, app).listen(PROXY_PORT);
} else {
  app.listen(PROXY_PORT);
}

console.log(`Serving on port ${PROXY_PORT}`);
