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

Build the companion from the same reviewed protocol-2 commit as the broker, not the historical alpha1 download. Open the app in Even Hub: the startup container is created **once at launch**, before authentication, and tells you to open the phone and enter the narrow device token. Connect/reconcile reuses the page; it does not repeat startup. If startup times out, close/reopen rather than guessing whether native creation succeeded. Confirm microphone permission and G2 connection. Tap to start, tap again to send; hold/release is an alternative. Double-tap discards recording or persists/requests stop, then calls `shutDownPageContainer(1)` for the system exit dialog, including before authentication and after local disconnect. A backend stop acknowledgement is not required to open that dialog; it is not proof of cancellation. If microphone shutdown is unconfirmed, the phone reports that fault rather than claiming safe exit.

The [contextual-menu guide](https://hub.evenrealities.com/docs/build/contextual-menu) documents a built-in Close action even without custom items; this companion does not add a redundant Exit menu item. Events 4/5 describe overlay entry/dismissal, not necessarily app shutdown. We conservatively discard capture on either overlay transition as well as actual exit events, and never restart recording automatically. Use phone controls when the OS intercepts gestures. R1 is optional and is not guaranteed to launch a closed/inactive companion.

**First blocking hardware test:** capture the actual installed-package Origin and prove authenticated broker access from that origin. If it is opaque/null or a custom scheme, it cannot pass the current strict policy. No compatible installed-package origin or alternative hosted beta path has been verified here. Do not whitelist null/wildcard or promise a hosted workaround. Browser software tests prove an HTTPS-page path, not native package connectivity.

Private/beta build instructions are not a marketplace-readiness declaration. The [submission guidelines](https://hub.evenrealities.com/docs/ship/app-submission) also cover content, safety, setup persistence and physical UX. Memory-only credentials intentionally require re-entry after close; the setup prompt is visible, but seamless remembered authentication is not claimed. Marketplace submission and its broader compliance review remain outside this preview.

## Optional native Even AI route (limited alternative)

The [official native-agent tutorial](https://support.evenrealities.com/hc/en-us/articles/16280926743695-Tutorial-Bridging-G2-to-OpenClaw-Bring-Your-Own-Agent) says EvenHub developer sign-up **and approval** unlock Agent Configuration. The public [article JSON](https://support.evenrealities.com/api/v2/help_center/en-us/articles/16280926743695.json) is an alternative when the article page is blocked.

The documented flow is Settings → Even AI → Agent Configuration → full `/v1/chat/completions` endpoint + API key → Save & Activate. Hermes exposes that compatibility endpoint, but **this native route is not the delivered companion protocol**, has not been hardware-tested here, and is not claimed to support this project's durable run control or phone approval UX. It uses a different, broader API credential. Only consider it with a dedicated constrained API/profile and your own verification. Never enter the companion device token into an unrelated native endpoint or place a master provider key there.

## Background limits

Official background-lifecycle and FAQ descriptions conflict about iOS networking while backgrounded. Assume the app must stay foregrounded. On visibility/offline/disconnect events the companion stops/discards capture best-effort. iOS can suspend JavaScript before cleanup completes: verify actual microphone shutdown and reconnection on hardware; if stop is unconfirmed, close the app/disconnect glasses. No hotword, ambient listening, background wakeup, locked-phone reliability or speaker output is promised.
