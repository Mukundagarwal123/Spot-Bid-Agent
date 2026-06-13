# Claude Plan Prompt - Multi-Source Carrier Aggregation

```text
Read these files first and confirm by listing them:
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/CLAUDE.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/features/feature-002-internal-turvo-carrier-recommendation.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/features/feature-003-dat-carrier-data-import.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/features/feature-004-freightx-carrier-relevancy-model.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/features/feature-005-multi-source-carrier-aggregation.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/data-model.md
- C:/Users/MukundAgarwal/PycharmProjects/Spot Bid Agent/docs/roadmap.md

Task:
Create an implementation PLAN ONLY for building the multi-source carrier aggregation layer.

Requirements:
1. Combine Source 1, Source 2, and Source 3 carrier rows into one outreach-ready dataset.
2. Keep `carrier_name`, `phone`, `email`, `mc_number`, and `source` in the merged output.
3. Deduplicate by MC number and carrier name.
4. Preserve source provenance in the `source` field, including label-style values like `1_2` or `1_4` when applicable.
5. Do not include outreach sending yet.

Deliver:
1. Backend data model plan
2. Aggregation and deduplication logic plan
3. API endpoint plan
4. Test plan
5. Rollout and migration notes
6. Open questions / assumptions
```
