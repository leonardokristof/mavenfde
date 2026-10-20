# Project charter

<!--
  Fill this in during TC1 Step 4, from your Getting to Concreteness form.
  Later weeks' notebooks read this file and stop if it is still the template.
  That is on purpose.
-->

**Department:** Hrvatski Telekom, fibre (FTTH) rollout

**Working title:** Fiberly

---

## The problem

**Who has it?** One real role, not a department.
It's affecting multiple roles, not one. 
My main users are the internal employees who handle fibre connection cases at Hrvatski Telekom. These include helpdesk and sales support agents, regional project managers (PMs), account managers (AMs), programme managers and field execution coordinators. They work in regional teams across Croatia, in Zagreb, Split, Osijek, Zadar, Rijeka and smaller towns. Most are experienced telecom professionals that use internal desktop tools all day. Their technical skills vary widely: some know the network data in depth, while others mainly deal with customers and requests. Many of them handle a steady flow of cases every day, often while a customer or a colleague from sales is waiting for an answer.

**What are they trying to do?**

Every day, project managers, account managers, the helpdesk, field teams and sales support need answers to the same questions: "Is fibre available at this address?", "What is happening with this customer's request?", "How long will it take?" and "Who is responsible?"

**How do they handle it today?**

Today, when an employee gets a question about fibre at an address, they answer it by hand. They open around five separate systems and combine the results themselves. First they look up the building's ADM ID in the address register. Then they check the network status, project and regulatory zone in the FIS FTTH forecast, and look for open requests and the current task in AAMS, plus a separate view for mini projects. In Pagesnap they read field progress, technicians' notes and who the assigned PM, AM and contractor are, and finally they find the responsible contact in the communication matrix.

After that they still have to interpret the data using rules that experienced colleagues know. Is a new request still blocked by the HAKOM stopwatch, which runs 30 days after activation in a regulated zone? How long does each type of task usually take? Has technical acceptance happened yet, which decides whether responsibility sits with the project team or with the matrix contact?

Unclear cases go to a few fixed fallback contacts: one person for addresses that are not in the system, and one for requests with no active task or no responsible person on record. New connection requests and fibre interest registrations are sent by email to a sales mailbox, with the customer's name, address, phone number and the package they want. The person checking also has to settle conflicts in the data by hand, such as duplicate building records, house numbers stored in different formats, and network status that disagrees with the field notes.

**What does that cost — time, money, risk, or relationships?**

A typical lookup means finding the building record, checking five systems, matching the data and applying the business rules. We estimate it takes 10 to 15 minutes per question, and complex cases take longer when a colleague has to be asked. With 50 to 100 questions a day, that is roughly 8 to 25 working hours every day, or 40 to 125 hours a week, about 175 to 525 hours a month, and around 2,000 to 5,500 hours a year. That is the equivalent of one to three full-time employees doing nothing but searching and cross-checking information. This figure does not include the hidden time spent by the few experts who get interrupted with unclear cases, or the time lost on follow-up calls when a customer gets a wrong or incomplete answer.

Those few experts and fallback contacts stay overloaded, because every unclear case ends up with them. Delays stay hidden until someone stumbles on them. Our pilot surfaced open requests that were 136, 192 and even 242 days past their expected deadline. HAKOM regulatory deadlines may be communicated wrongly to customers, which puts the company at compliance risk. Customers whose building already has fibre in the street wait longer to be connected, which slows down the return on the money we have already put into the rollout. Knowledge stays in the heads of a few people, so the process breaks whenever they are unavailable or leave.

**The problem in one sentence. No solution in it.**

To answer just one question about fibre at an address, an employee has to check up to six separate systems and interpret what they found using rules that mostly exist only in people's heads, so the answers are slow, inconsistent and depend on who you ask.

---

## Success

**What does the new world look like for that person?**

Every employee gets the same answer, based on the same rules, with all the information in one place. Answers no longer depend on who you ask. The assistant also says clearly when it does not know something, instead of guessing. In our pilot, a full answer took about 25 seconds and a follow-up question about 10 seconds. Teams also communicate more easily, because everyone works from the same answer and the same named contact, instead of chasing each other for information.

Once this is automated, users can spend their time on higher value work. They can unblock delayed cases, escalate overdue requests, coordinate field work and keep customers informed. The few experts who answer everyone's questions today can focus on the hard exceptions that really need their judgement.

**How would the firm measure it? Which numbers should move?**

**Faster.** An answer that today takes 10 to 15 minutes of manual searching across five systems arrives in about 25 seconds, and follow-up questions take about 10 seconds. Cases move faster, so customers get connected to fibre sooner.

**Cheaper.** By our estimate, the assistant frees up around 2,000 to 5,500 working hours a year, the equivalent of one to three full-time employees.

**Lower risk.** Overdue requests that used to go unnoticed for months are flagged automatically, with a named person to escalate to.

**Revenue and customer experience.** When a building already has fibre in the street, faster processing means the customer is connected and paying sooner. Customers get quicker and more accurate answers, wait less and call back less often.

I would test it with three to five operators on their real cases for one day. Next to each answer, they would note whether it was correct and how long the same check would have taken them by hand.

---

## The first product

**Your solution in one sentence.**

An AI fibre assistant for Hrvatski Telekom's helpdesk, sales support, project managers and field execution coordinators. It takes an address, ADM ID or AAMS request number typed in plain language and gives a short, ready-to-use answer about fibre availability, HAKOM stopwatch status, the open request, missed deadlines and who to contact. This cuts each lookup from 10 to 15 minutes across six systems to under a minute.

**Input → Output.** Be specific enough that someone could build it wrong and you
would notice.

| | |
| --- | --- |
| **In** | The user opens a simple chat window and types a question in plain language, the way they would ask a colleague. The question contains an address, an ADM ID or an AAMS request number, often with typos or missing diacritics. If something is missing, the user answers the assistant's question with the city or the ID type ("Novigrad", "ADM ID"). After that they keep the conversation going with short follow-ups ("which ticket is it?", "who is the PM?") and yes or no answers to the one suggested next step ("Have you already submitted a connection request?"). The app adds their identity and session automatically in the background. |
| **Out** | The system writes a short, ready-to-use answer in a colleague's tone, so the operator can immediately tell the customer or a colleague what is going on. The answer starts with the fibre status of the building and what it means ("fibre is in the street but not yet connected to the building, construction work is needed, expected within 90 days"). If the HAKOM stopwatch is active, the answer gives that first, with the exact expiry date ("new connection requests can't be accepted until 31.10.2026"). It then describes any open request: the current task, what it means and how long it usually takes. If a deadline has been missed, it says by how many days and recommends a specific person to escalate to ("242 days past the deadline, I suggest escalating to [name]"). The answer can also include short notes, for example that another open request or a second building record exists for the same address. It ends with at most one suggested next step ("Have you already submitted a connection request?") and a fixed summary line ("ADM ID: X \| Status: Y \| Project: Z"). When the address or ID doesn't exist, the output is a single honest sentence saying so and naming who to contact, instead of a guess. |

---


## Decisions made later

<!--
  Amended as the cohort goes. Keep the reasoning, not just the choice — Week 5
  asks you to defend your architecture against the options you rejected, and
  Week 10's handoff doc is largely this section.
-->

| Week | Decision | Why, and what you rejected |
| --- | --- | --- |
| 3 | Retrieval approach | <!-- TC3 --> |
| 5 | Agent architecture | <!-- TC5 --> |
| 8 | Model | <!-- TC8 --> |
