# Stakeholders

Everyone you talk to about this project, from the first "where would this even
run?" to the final readout.

> **Week 10's technical challenge is a report to the people in this file.**
> You cannot write it later from memory. Add a row the day you have the
> conversation.

Use roles, not names. This is a public repo.

| Week | Who (role) | What you asked | What you learned | Follow-up |
| --- | --- | --- | --- | --- |
| 1 | DevOps team, and colleagues who have worked with them | Where a container would run, which cloud, the registry, login, internet access, secrets, who approves a deployment, and whether there is an approved LLM endpoint | A managed container service on GCP or Azure; secrets from the cloud's secret manager; Entra ID login; DevOps, Information Security and the Data Protection Officer approve; several LLM endpoints already exist, but from a laptop they sit behind the authenticated proxy | Which cloud this app goes to, and which LLM endpoint is approved for data that contains personal information |
| 1 | Representative of the field services, operations and construction sector, who asked for this tool in the first place | Worked through the use case and the five golden examples with him | He is happy with the use case and found the golden examples solid. Nothing to change | His answers to the three Step 12 questions: what he would use it for, what is missing, what he expects it to cost |

---

## Not everyone is an infrastructure contact

The useful list is wider than it first looks, and Week 10's report goes to all of
them:

- **The person with the problem** — the one from your charter. Have you shown
  them anything yet?
- **Whoever owns the data** you would need.
- **Whoever runs the platform** your app would deploy onto.
- **Whoever approves** a deployment, a spend, or a vendor.
- **Your own manager**, who will be asked whether this was worth the ten weeks.

If a week goes by with no conversation, add a row saying so and why. A visible
gap is more useful than a silent one.
