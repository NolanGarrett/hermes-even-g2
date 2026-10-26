# Private networking and credentials

The broker listens only on loopback (default `127.0.0.1:8766`). Put an operator-managed HTTPS reverse proxy in front of it, reachable through your existing private network. No relay is required. Do not expose the full Hermes API to the phone just to reach this broker.

## VPN-neutral examples

- WireGuard: the phone joins your existing tunnel; private DNS resolves `g2.example.com` to your private reverse proxy. Allow the phone only the proxy's HTTPS port, not SSH/admin/API ports.
- Tailscale: use a private DNS name with a certificate trusted by the phone, or a custom hostname routed privately. Tailnet membership does not replace the device bearer or CORS.

These are topology examples, not automatic installers. This repository does not create VPNs, accounts, firewall rules, certificates or public tunnels. The example domain is reserved and serves no project service.

Example nginx location inside an existing TLS virtual host (provide your own trusted certificate and private listener):

```nginx
server {
    listen 443 ssl;
    server_name g2.example.com;
    ssl_certificate /etc/ssl/private/g2-fullchain.pem;
    ssl_certificate_key /etc/ssl/private/g2-key.pem;
    client_max_body_size 1m;
    location / {
        proxy_pass http://127.0.0.1:8766;
        proxy_set_header Host $host;
        proxy_set_header Origin $http_origin;
        proxy_set_header Authorization $http_authorization;
        proxy_read_timeout 40s;
        proxy_buffering off;
        access_log off;
    }
}
```

Do not add permissive proxy CORS headers or strip Origin. Keep TLS verification enabled. If using an internal CA, install/trust it using your phone's supported administration flow, then validate it inside the Even WebView; Safari trust alone is not evidence. For a public CA, obtain a certificate without making your service public (for example DNS validation). WSS is not required by this implementation: the companion uses HTTPS requests/status polling and the broker consumes backend SSE internally.

There are two independent origin gates:

1. `companion/app.json` network whitelist contains the **broker origin**, e.g. `https://g2.example.com`. Exact scheme/host/port; no path or wildcard. Rebuild after changing it.
2. Broker `origins` contains the **WebView page origin**, e.g. `https://companion.example.com`. It may differ. Non-browser authenticated requests may omit Origin; requests with untrusted/null origins fail. Credentials remain mandatory.

Host the static `companion/dist/` at your trusted page origin for hosted development, or use the supported Even beta flow. Avoid third-party scripts, analytics and public embedding. Static hosting must not transform the app or inject scripts. Use no-store caching for credential-bearing API replies; the client sets `cache: no-store` and never sends cookies.

## Separation and revocation

- Hermes API key: server-to-server only; set `EVEN_G2_BACKEND_KEY` to the intended API key.
- STT key: server-to-provider only; `EVEN_G2_STT_KEY`.
- Device token: random unique 32+ characters, phone memory only. Broker stores only SHA-256 digest associated with a device label. Maximum 16 devices.

A stolen device token remains powerful: it can ask the configured agent to use tools. Rotate/revoke via broker config and restart your broker. Removing a token does not cancel a previously accepted run. Never place tokens in URLs, app manifests, source, localStorage or shared screenshots. Do not use the native Even AI endpoint's broad API credential as a companion token.
