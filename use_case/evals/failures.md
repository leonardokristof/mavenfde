# Failures

Fifty traces from the endpoint (`answer_from_records`), read on 2 November 2026. The inputs are 50 rows of the generated corpus: two from every record state, the rest spread over the intents, paths and message forms. The run cost $0.0126. Each answer was read next to the answer the data expects, with one sentence written for every failure.

**16 of the 50 traces were failures.**

| # | Failure | Count |
| --- | --- | --- |
| 1 | A request it must refuse (SQL, personal data, changing data, an off-topic question) gets the one line "Mogu pomoći samo s mrežnom infrastrukturom." or a request for an ID, without saying what it will not do and what it can check instead | 8 |
| 2 | Two similar streets, or two records for one building, come back as "not recorded" instead of a question back. The ambiguous records exist only in the clarification rows of the data, and the store holds only answered rows, so the endpoint never sees them | 4 |
| 3 | A bare number is taken as an AAMS number and reported as not found, instead of asking whether it is an ADM or an AAMS number | 1 |
| 4 | A greeting gets "Trebam adresu, ADM ID ili AAMS broj" instead of a friendly reply | 1 |
| 5 | The model changed the meaning of a record: "the project has no PM either" became "there is no project FTTH_PULA_3", while the ID line names that project | 1 |
| 6 | When the field data and the network status disagree, the answer gives the field data without saying the network shows something else | 1 |

The other 34 match the expected answer, or differ from it and are still right. In one, the endpoint found a second building at the same address that the expected answer did not know about. In another, it asked whether a bare number is an ADM or an AAMS number where the data assumed ADM.
