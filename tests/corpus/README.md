# 자료 모음

표 읽기 규칙(`web/js/tabledata.js`)의 기준이 되는 파일이다. `tools/rules_check.mjs` 가 파일마다 같은 이름의 `.expect.json` 에 적은 대로 읽히는지 본다 (`pytest` 의 `test_rules`).

- 실제 자료의 **형식**을 본뜬다. 공개 저장소이므로 수치·품목·기관 이름은 바꿔서 넣는다.
- 파일을 더할 때 `.expect.json` 도 같이 만든다. 적은 값만 비교한다: `regions`, `plain`, `freq`, `first`, `last`, `points`, `series`, `units`.
- 잘못 읽힌 파일을 발견하면 그 형식을 여기에 먼저 넣고 규칙을 고친다.
- 지금은 csv·tsv 만 읽는다. xlsx 는 아직 없다.
