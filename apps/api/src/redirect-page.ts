import { randomBytes } from "node:crypto";

import { escapeHtml } from "@urltrack/shared";

export type RedirectPageInput = {
  apiBasePath?: string;
  destinationUrl: string;
  visitToken: string;
};

export function buildRedirectPage(input: RedirectPageInput): { html: string; nonce: string } {
  const nonce = randomBytes(16).toString("base64url");
  const apiPath = input.apiBasePath ?? "/api/v1/fp";
  const destinationLiteral = JSON.stringify(input.destinationUrl);
  const tokenLiteral = JSON.stringify(input.visitToken);
  const apiPathLiteral = JSON.stringify(apiPath);

  return {
    nonce,
    html: `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="refresh" content="2;url=${escapeHtml(input.destinationUrl)}">
  <title>Redirecting...</title>
  <style nonce="${nonce}">
    body{margin:0;background:#0A0A0A;color:#F5F5F5;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;display:grid;min-height:100vh;place-items:center}
    main{width:min(420px,calc(100vw - 32px));border:1px solid #2A2A2A;background:#141414;padding:24px}
    .bar{height:3px;background:#2A2A2A;overflow:hidden}.bar:before{content:"";display:block;height:100%;width:42%;background:#00C853;animation:load 900ms infinite alternate}
    p{color:#888888;margin:12px 0 0;font-size:14px}@keyframes load{to{transform:translateX(150%)}}
  </style>
</head>
<body>
  <main>
    <div class="bar"></div>
    <p>Preparing secure redirect...</p>
    <noscript><p><a href="${escapeHtml(input.destinationUrl)}">Continue</a></p></noscript>
  </main>
  <script nonce="${nonce}" type="module">
    import { getFingerprint } from "https://cdn.jsdelivr.net/npm/@thumbmarkjs/thumbmarkjs/dist/thumbmark.esm.js";
    const destinationUrl = ${destinationLiteral};
    const visitToken = ${tokenLiteral};
    const apiPath = ${apiPathLiteral};
    try {
      const thumbmark = await getFingerprint({ experimental: true });
      const payload = JSON.stringify({ visit_token: visitToken, thumbmark });
      navigator.sendBeacon(apiPath, new Blob([payload], { type: "application/json" }));
    } catch {
      // Fingerprinting is best-effort and must never block the redirect path.
    } finally {
      window.location.replace(destinationUrl);
    }
  </script>
</body>
</html>`
  };
}
