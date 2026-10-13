# Someone else's ecosystem

Where your application would actually run, inside your actual firm.

> **Week 1 starts this file. Week 9 finishes it.**
> TC1 Step 6 asks eight questions. The full Week 9 checklist has around thirty,
> and the eight are a strict subset — so nothing here gets thrown away.

Describe patterns, not specifics. "On-prem OpenShift, images from an internal
registry, no public egress" is useful to everyone and identifies nobody. Never
put real hostnames, IPs, or architecture diagrams in this file.

---

## Week 1 — the first eight questions

<!-- Answered in TC1 Step 6. Bring these back from a real conversation. -->

**Who did you ask?** (role, not name)

Not asked yet. The answers below are what I measured on my own machine during
setup and what I already know from earlier internal AI work. Everything marked
*(to confirm)* goes to the DevOps team and Information Security in TC1 Step 6.

| # | Question | Answer |
| :---: | --- | --- |
| 1 | Where do internal apps run? (k8s, ECS, App Service, a VM someone maintains) | Internal automation and AI workflows run on a self-hosted low-code workflow platform operated by the DevOps team. Where a containerised app would run is *(to confirm)*. |
| 2 | Which cloud? AWS, Azure, GCP, on-prem, several? | The data warehouse and source systems appear to run in the company's own data centre *(to confirm)*. GCP (Vertex AI) and Azure (AI Foundry) are both used for AI models. Other cloud use *(to confirm)*. |
| 3 | Is there an internal container registry? | *(to confirm)* |
| 4 | How do users log in? (Okta, Entra ID, Ping, SAML, homegrown) | *(to confirm)* |
| 5 | Can the app reach the internet? Egress proxy? Allowlist? | Only through the corporate web proxy, configured on laptops by a PAC file. TLS is intercepted with a corporate CA. Direct connections to public package registries time out. |
| 6 | Where do secrets come from? (Vault, Secrets Manager, Key Vault) | *(to confirm)* |
| 7 | Who approves a deployment, and what review does it need? | *(to confirm)*. Expected: DevOps for the platform, Information Security for data access and the agent's tools, and the Data Protection Officer because the data contains personal information. |
| 8 | Is there an approved internal LLM endpoint already? | Partly. A company Azure AI Foundry resource (R&D playground) has GPT and Claude deployments with key auth: GPT models through the Azure OpenAI route, Claude models only through the Anthropic-compatible route (`x-api-key`, not `api-key`). Claude is also available through Vertex AI in a development GCP project, and Claude Code runs through a corporate gateway. From a laptop all of these sit behind the authenticated proxy. Which one is approved for production, and on what data, *(to confirm)*. |

**What surprised you?**

<!-- your answer here -->

**What would you have to change about your app to deploy there?**

<!-- your answer here -->

---

## Week 1 — what your machine told you

<!--
  Paste the egress probe output from Session 1 here. It is evidence, and it
  frequently disagrees with what people believe about their own network.
-->

<!-- probe output here -->

### Setup findings (prerequisites, before Session 1)

| Finding | What it means | Workaround used |
| --- | --- | --- |
| `uv sync` timed out connecting to the public package registry | No direct egress; tools that do not read the PAC file cannot reach the internet | Set `HTTPS_PROXY` / `HTTP_PROXY` to the corporate proxy for the command, plus `uv --native-tls` so the corporate CA from the Windows store is trusted |
| The proxy lets some hosts through anonymously (public package registry) but answers `407 Proxy Authentication Required` for the cloud LLM endpoint; with Windows NTLM credentials the request reaches the endpoint | Egress to AI providers is per-destination and authenticated. Python HTTP clients (LiteLLM / httpx) cannot do NTLM proxy auth, so the app cannot reach the model from a laptop as-is | *(open)* Options: a local NTLM-forwarding proxy on localhost, an allowlist exception for the LLM endpoint, or an internal LLM gateway reachable without the proxy. To decide with Information Security / DevOps |
| Corporate CA bundle already set for Node (`NODE_EXTRA_CA_CERTS`) | TLS is intercepted for all outbound traffic | Use the OS certificate store or the CA bundle; never disable verification |
| No container runtime allowed on the managed laptop (Docker Desktop not permitted, WSL not installed, so Rancher and Podman are not an option either) | Containers cannot be built or run locally; the Week 1 container step and Week 9 deployment need another place to build | Build and run the container in a cloud dev environment (GitHub Codespaces) on synthetic data only; ask DevOps how containers are built today (CI pipeline, internal build service) |
| `python` resolved to the Microsoft Store stub | PATH order problem on a managed Windows laptop | Put the python.org install ahead of the Store alias in the user PATH |
| Claude Code uses a custom base URL (corporate gateway) | Coding agent traffic is already routed through a sanctioned company path; remote features tied to the public API are unavailable | None needed |

**Does this match what you were told in the table above?** Where it doesn't, that
gap is worth chasing — it usually means a proxy nobody documented.

---

## Week 9 — the full checklist

<!--
  TC9 extends this same file. Do not start a new one: the point is that the git
  history shows one continuous piece of work from Week 1 to Week 9.
-->

<!-- Week 9 -->
