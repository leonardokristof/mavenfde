# The ecosystem you deploy into

Where your application would actually run, inside your actual firm.

> **Week 1 starts this file. Week 9 finishes it.**
> TC1 Step 10 asks eight questions. The full Week 9 checklist has around thirty,
> and the eight are a strict subset — so nothing here gets thrown away.

Describe patterns, not specifics. "On-prem OpenShift, images from an internal
registry, no public egress" is useful to everyone and identifies nobody. Never
put real hostnames, IPs, or architecture diagrams in this file.

---

## Week 1 — the first eight questions

<!-- Answered in TC1 Step 10. Bring these back from a real conversation. -->

**Who did you ask?** (role, not name)

DevOps and colleagues that I know that worked with DevOps team.

| # | Question | Answer |
| :---: | --- | --- |
| 1 | Where do internal apps run? (k8s, ECS, App Service, a VM someone maintains) | As a container on a managed cloud service, most likely Cloud Run on GCP or Azure Container Apps on Azure. Both run the same Docker image, so no rework. |
| 2 | Which cloud? AWS, Azure, GCP, on-prem, several? | Several. GCP and Azure are the ones used most often. Which one for this app |
| 3 | Is there an internal container registry? | Expected: the registry of whichever cloud the app runs on (Artifact Registry on GCP, Container Registry on Azure). Since direct connections to public registries time out from the corporate network, pulling base images from Docker Hub is likely blocked too. |
| 4 | How do users log in? (Okta, Entra ID, Ping, SAML, homegrown) | Expected: Entra ID single sign-on with work accounts, since that's what employees already use. |
| 5 | Can the app reach the internet? Egress proxy? Allowlist? | Only through the corporate web proxy, configured on laptops by a PAC file. TLS is intercepted with a corporate CA. Direct connections to public package registries time out. |
| 6 | Where do secrets come from? (Vault, Secrets Manager, Key Vault) | The cloud's own secret manager (Secret Manager on GCP or Key Vault on Azure) instead of a .env file. |
| 7 | Who approves a deployment, and what review does it need? | DevOps for the platform, Information Security for data access and the agent's tools, and the Data Protection Officer because the data contains personal information. |
| 8 | Is there an approved internal LLM endpoint already? | Yes, we have multiple endpoints that we can use, GCP, Azure, internal platform ... |

**What surprised you?**

The big difference between my personal computer and my work laptop. On my personal machine everything just works, but on the work laptop I can't really do anything without first contacting IT to get permission to install WSL or any other tool. On top of that, every outbound connection goes through an authenticated proxy with TLS interception, and public package registries aren't reachable directly. So before writing a single line of code, the setup itself depends on other teams.

**What would you have to change about your app to deploy there?**

- Build from base images and packages available through the internal registry and proxy, not straight from Docker Hub and PyPI
- Trust the corporate CA inside the container, so outbound TLS calls through the proxy don't fail on certificate errors
- Push the image to the internal registry of the chosen cloud
- Read secrets from the cloud's secret manager instead of a .env file
- Put Entra ID login in front of the app
- Point the model to the approved endpoint, for example GPT through Vertex AI or Claude through Azure, which with LiteLLM is a change in environment variables, not in the code
- Serve frontend libraries from the app itself instead of a public CDN
- Get approval from Information Security and the Data Protection Officer for the data the app reads and the tools it can call

---

## Week 1 — what your machine told you


### 2026-10-13 · personal laptop, off the corporate network

Session 1 egress probe (`helpers.preflight.check_egress`): the default hosts plus
`api.anthropic.com`, the model API this app actually calls.

| Host | Why | Status | Signed by |
| --- | --- | --- | --- |
| `pypi.org` | Python packages | OK | GlobalSign nv-sa |
| `files.pythonhosted.org` | the actual wheel downloads | OK | GlobalSign nv-sa |
| `api.openai.com` | the model API | OK | Google Trust Services |
| `cdn.jsdelivr.net` | the CDN the Week 1 frontend uses | OK | Sectigo Limited |
| `huggingface.co` | open weights, Weeks 2 and 8 | OK | Amazon |
| `registry-1.docker.io` | container images | OK | Amazon |
| `github.com` | this repository | OK | Sectigo Limited |
| `api.anthropic.com` | the model API this app actually uses | OK | Google Trust Services |

**Verdict:** Open network, public CAs, no proxy. Nothing here will bite you.
8/8 reachable, no proxy or CA variables set.

### Setup findings: corporate laptop (prerequisites, before Session 1)

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

**This was all run through VPN that's why the results are like this. Without VPN connection some of it goes through.**

### Setup findings: personal laptop (prerequisites, 2026-10-13)

| Finding | What it means | Workaround used |
| --- | --- | --- |
| Git, Docker Desktop, Python 3.14, uv and Claude Code installed with no approvals; `setup_check.sh` passed with two warnings | Nothing on this machine depends on IT | None needed |
| `uv sync` reached the public package registry directly | No proxy and no corporate CA, nothing to configure | None needed |
| Docker Desktop is allowed; the daemon only had to be started | The Week 1 image builds and runs here. `/health` and `/chat` answer from the container, it runs as a non-root user and `.env` is not in the image | Start Docker Desktop before building |
| The model is called directly through the Anthropic API with a personal key | No proxy authentication in the way, a test message came back in 1.3 seconds. A personal key is not a company-approved endpoint | Only synthetic data on this machine; real data only on the approved company endpoint |
| `python` is not on the PATH, only `python3` | macOS has no `python` alias by default | `uv run python` picks the interpreter itself |
| Claude Code runs on a personal subscription, not the corporate gateway | Nothing goes through a company-controlled path, so the privacy settings are up to me | "Help improve Claude" switched off; local `.claude/settings.json` blocks reading `.env` and `use_case/data/` and turns off telemetry |

---

## Week 2 · local models

Personal laptop (Apple M5, 16 GB): models up to about 2B run in float16 on the GPU without trouble (Qwen3-1.7B: 8 messages of up to 40 tokens in about 2 s, *measured*); the 4–8B tier should fit when quantised (*looked up*, course table). Work laptop: not tested, and unlikely without approvals, since there are no admin rights, no container runtime, and huggingface.co was never probed from the corporate network. To ask DevOps: is there an internal model registry, or a GPU host where a model could run inside HT?

Local model: plausible for HT only on a GPU host inside the company. On the laptop, qwen3:8b through Ollama answered all five goldens word for word with a two-line change in `.env` and no code changes, but took 13 to 29 s a question against 1 to 2.5 s on Claude, and timed out after 60 s once (*measured*). For it to work at HT: a GPU server approved by DevOps, model weights from an approved registry (ollama.com and huggingface.co weren't tested from the corporate network), and a timeout and p95 target set for local speed.

---

## Week 3 · retrieval

Personal laptop, *measured* on 27 October: the BM25 index over the 1,705 answered records builds in 0.05 s inside the app. The image, built from the lock with `rank-bm25` added, grew by 74 KB to 807 MB. The records are not in the image: they are mounted read-only at run time and the path comes from `CORPUS_PATH`, the same rule as the key. The hybrid I measured and did not ship embedded the corpus with a local multilingual model, 175,930 tokens for $0, and nothing left the machine. The Anthropic API has no embedding endpoint, so dense retrieval with one key means a local model or a second provider, and at work a second approval.

At work the shipped technique needs no embedding model, no vector database and no index anyone has to own. It needs read access by key, an ADM ID, an AAMS number or an address, through the query layer the source databases already sit behind, offered as read-only tools that the company's agent platform calls through its API gateway. To settle for Week 9: who owns that connection and how fresh its data is; whether the gateway passes on the operator or only the calling app, because a filter on which buildings and fields a role may see has to sit in the tool, before anything is returned; and which endpoint is approved for the answer model, since the records hold addresses and contacts.

---

## Week 9 — the full checklist

<!--
  TC9 extends this same file. Do not start a new one: the point is that the git
  history shows one continuous piece of work from Week 1 to Week 9.
-->

<!-- Week 9 -->
