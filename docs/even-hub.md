# Even Hub build and installation

**HARDWARE UNVERIFIED.** This project does not publish to the Even marketplace or create developer accounts. You supply your own enrollment/approval and privately deploy the broker.

## Deployment-specific build

Use Node 22.12+ and npm. The actual SDK and CLI versions are locked in `package-lock.json`.

1. Edit `companion/app.json`: set network permission `whitelist` to your broker's exact HTTPS origin. Preserve microphone permission and minimum app/SDK versions. Do not put any token in this file.
2. Optionally change the visible endpoint default in `companion/index.html`; it is just a convenience, not the policy. The runtime transport reads the manifest whitelist.
3. Run `npm ci`, `npm test`, `npm run build`, `npm run pack` from `companion/`.
4. The CLI writes `hermes-even-g2.ehpk`. Keep the license notices included under the built static root. The initial release `.ehpk` is a reserved-origin deployment template; rebuilding is required for real private use.

The pinned SDK 0.0.16 declares an Even App minimum of 2.2.10. Do not remove that floor. A valid ZIP/package stamp does not prove device installation or developer-account permission.

## Developer/beta access

Follow the current [Even developer portal](https://hub.evenrealities.com/) and [beta guide](https://hub.evenrealities.com/docs/test/beta-testing). Enroll yourself; account terms/approval are outside this project. Upload your package with the portal/official CLI, register your tester, promote the build from **Private to Beta**, and ensure the tester is **Active**. Beta, not a local browser preview, is required to test glasses menu placement and published lifecycle behavior.

Open the app in Even Hub. Enter the broker origin and narrow device token on the phone. The startup text container is created before enabling glasses audio. Confirm microphone permission and G2 connection. Tap to start, tap again to send; hold/release is an alternative. Use the phone buttons when the OS intercepts gestures. R1 is optional and is not guaranteed to launch a closed/inactive companion.

If a packaging mode has opaque/null WebView Origin, it cannot pass this broker's exact-origin policy. Use a supported HTTPS-hosted/beta origin and validate the actual Origin. Do not whitelist null or wildcard to make it work.

## Optional native Even AI route (limited alternative)

The [official native-agent tutorial](https://support.evenrealities.com/hc/en-us/articles/16280926743695-Tutorial-Bridging-G2-to-OpenClaw-Bring-Your-Own-Agent) says EvenHub developer sign-up **and approval** unlock Agent Configuration. The public [article JSON](https://support.evenrealities.com/api/v2/help_center/en-us/articles/16280926743695.json) is an alternative when the article page is blocked.

The documented flow is Settings → Even AI → Agent Configuration → full `/v1/chat/completions` endpoint + API key → Save & Activate. Hermes exposes that compatibility endpoint, but **this native route is not the delivered companion protocol**, has not been hardware-tested here, and is not claimed to support this project's durable run control or phone approval UX. It uses a different, broader API credential. Only consider it with a dedicated constrained API/profile and your own verification. Never enter the companion device token into an unrelated native endpoint or place a master provider key there.

## Background limits

Official background-lifecycle and FAQ descriptions conflict about iOS networking while backgrounded. Assume the app must stay foregrounded. On visibility/offline/disconnect events the companion stops/discards capture best-effort. iOS can suspend JavaScript before cleanup completes: verify actual microphone shutdown and reconnection on hardware; if stop is unconfirmed, close the app/disconnect glasses. No hotword, ambient listening, background wakeup, locked-phone reliability or speaker output is promised.
