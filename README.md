# Lee Humanities Research

**한국어 인문학 연구·집필·검증을 위한 Academic Research Skills 포크**

[원본 ARS](https://github.com/Imbad0202/academic-research-skills) · [변경 이력](CHANGELOG.leehumanities.md) · [원본과의 관계](UPSTREAM.md) · [라이선스](LICENSE)

이 배포판은 철학적·계보학적 논문, 개념사, 미디어 이론, 사이버문학 연구를 위한 Claude Code 플러그인입니다. 연구자가 제공한 정본과 원전을 읽고, 외부 선행연구와 반론을 조사하며, 실제로 분리된 역할을 호출해 원고를 검토합니다.

- 논문의 흐름: **문제제기 → 계보 → 핵심 논증 → 확장 → 결론**. 원고와 저널 요구에 따라 조정합니다.
- 저자의 개념 정의, 외부 학설, 원문 증거, AI의 해석을 구분합니다.
- 원전·번역본·판본·인쇄 쪽수·PDF 쪽수와 실제 읽은 범위를 기록합니다.
- 인용 감사와 심사 기록은 본문 밖에 보관합니다.
- 국문·영문 초록과 수정 전후의 개념·수치·인용 변화를 확인합니다.
- 연구 원고와 개인 접속 정보는 이 저장소에 넣지 않습니다.

## 빠른 설치

Claude Code가 설치된 터미널에서 실행합니다. 원본 ARS와 다른 이름으로 설치됩니다.

```sh
claude plugin marketplace add icerain-cmd/academic-research-skills-leehumanities
claude plugin install leehumanities-research@leehumanities --scope user
claude plugin list
```

Claude Code의 대화 안에서는 다음 명령을 사용합니다.

```text
/plugin marketplace add icerain-cmd/academic-research-skills-leehumanities
/plugin install leehumanities-research@leehumanities
```

설치 후 새 Claude Code 대화에서 시작합니다. 기존에 열려 있던 세션은 설치 전 플러그인 상태를 유지할 수 있습니다.

```text
/leehumanities-research:doctor
```

계정 로그인 만료 메시지가 표시되면 터미널에서 `claude auth login`으로 로그인한 뒤 새 대화를 엽니다. 플러그인 설치와 Python 검사는 계정 인증 없이 가능하지만, 논문 집필과 역할별 검토에는 유효한 Claude 로그인이 필요합니다.

### 확인 기능을 포함한 설치 도구

```sh
git clone https://github.com/icerain-cmd/academic-research-skills-leehumanities.git
cd academic-research-skills-leehumanities
python tools/leehumanities/install.py --dry-run
python tools/leehumanities/install.py
```

Windows PowerShell에서는 `./tools/leehumanities/install.ps1`, macOS/Linux에서는 `bash tools/leehumanities/install.sh`도 사용할 수 있습니다. 설치 도구는 현재 CLI의 도움말을 확인하고 사용자 범위에 설치한 뒤 활성 상태를 확인합니다. 같은 이름으로 다른 마켓플레이스가 등록되어 있으면 중단합니다. 기존 스킬을 삭제하거나 설정 파일을 통째로 교체하지 않습니다.

업데이트는 `python tools/leehumanities/install.py --update`로 수행합니다. 설치되지 않은 구형 CLI에서는 자동 복사를 시도하지 않고 지원되는 설치 경로를 안내합니다.

## 명령

| 명령 | 용도 | 예시 |
|---|---|---|
| `/leehumanities-research:plan` | 문제의식·개념 계보·장 구성 | `제공한 메모로 철학적 논문의 장 구성을 설계해` |
| `/leehumanities-research:research` | 정본과 외부 선행연구·반론 조사 | `이 개념의 계보와 가까운 이론의 차이를 원전으로 검토해` |
| `/leehumanities-research:write` | 인문학 논문 초고와 별도 감사 | `제공 자료에 근거해 전체 초고를 새 파일에 작성해` |
| `/leehumanities-research:review` | 독립된 논증 비판·출처 검증 | `원고.md를 검토하고 근거가 있는 지적만 별도 파일에 남겨` |
| `/leehumanities-research:citations` | 서지·쪽수·주장-출처 관계 | `원고와 원문 폴더의 인용을 확인해` |
| `/leehumanities-research:revise` | 심사 대응·수정 및 재검토 | `심사 의견을 반영해 사본을 수정하고 대응표를 작성해` |
| `/leehumanities-research:abstract` | 국문·영문 초록 | `국문 700자 안팎, 영문 200단어 이내 초록을 작성해` |
| `/leehumanities-research:corpus` | 명시한 자료 폴더의 읽기 전용 색인 | `자료 폴더를 별도 작업 폴더에 색인해` |
| `/leehumanities-research:doctor` | 설치 구성·도구·사용 가능 범위 점검 | `현재 설치 상태를 확인해` |

자연어로 요청할 때도 `Lee Humanities Research`를 명시하면 원본 ARS 등 다른 연구 스킬과 구분하기 쉽습니다. 논문 작성을 요청하면 승인된 범위의 실제 본문을 작성합니다. 계획만 요청한 경우에는 계획까지만 작성합니다.

## 역할과 실제 실행

| Claude 하위 에이전트 | 연구 역할 | 주요 책임 |
|---|---|---|
| `lh-theorist` | HeHe 역할: 이론 구성 | 문제의식, 개념의 계보, 외부 이론과 차이 |
| `lh-argument-critic` | HeCo 역할: 반론·논증 | 전제와 결론, 반례, 개념 중복, 과잉 일반화 |
| `lh-source-verifier` | HeCl 역할: 출처 검증 | 원문·판본·인용 위치·읽은 범위·주장 근거 |
| `lh-style-editor` | 한국어 문체 편집 | 저자 목소리, 사유의 전개, 국영문 의미 대응 |

주 대화가 편집과 진행을 맡습니다. 검토 시 논증 비판자와 출처 검증자는 같은 원고를 별도 문맥에서 읽고, 서로의 판정을 미리 받지 않습니다. 문체 편집은 내용 검토 후 수행합니다. 실제 호출한 역할, 모델 정보가 노출된 경우의 모델명, 읽은 자료와 범위를 기록합니다. 하위 에이전트 기능을 사용할 수 없으면 순차 실행으로 축소된 사실을 표시합니다.

**기본값은 모든 역할이 현재 Claude 모델을 상속하는 것입니다.** 역할 분리는 여러 회사의 모델을 사용한 교차 검증을 뜻하지 않습니다. 기존 Hermes 봇이나 운영 중인 공용 기억을 자동으로 연결·수정하지 않습니다.

### 선택적인 MCP 문헌 조회

1.0.1부터 이론 구성자와 출처 검증자는 기존에 연결된 `jj-academic-korea`, `semantic-scholar`, `jj-filesystem`의 지정된 검색·조회 도구를 직접 사용할 수 있습니다. `ToolSearch`와 개별 도구 이름을 허용하며, MCP 전체나 파일 쓰기·삭제·실행 도구는 허용하지 않습니다. 이 플러그인은 서버를 설치하거나 키와 접속 정보를 배포하지 않습니다. 해당 서버가 없는 환경에서는 기본 읽기·웹 도구와 부모 세션이 제공한 출처·열람 기록을 사용합니다.

RISS 도구는 검색어·검색 URL·수동 확인 목록을 만드는 보조 기능입니다. 그 응답만으로 RISS를 검색했거나 문헌을 확인했다고 표시하지 않습니다. 서버 연결, 도구 호출 성공, 서지 확인, 원문 열람과 주장 검증은 각각 따로 기록합니다.

## 자료와 결과의 위치

사용자가 지정한 원문 폴더를 읽고, **원문 폴더 및 설치된 플러그인 밖의 작업 폴더**에 결과를 씁니다. 일반적인 작업 위치는 연구 프로젝트의 `.leehumanities/runs/<run-id>/`입니다. 원문 전체가 같은 프로젝트 루트에 있다면 작업 폴더를 별도의 형제 디렉터리에 두거나 실제 원문 하위 폴더를 지정합니다.

원문, 원고, 파일 경로, 읽은 기록, 검증 기록은 비공개 연구 자료입니다. 이 공개 저장소와 설치된 플러그인에는 보관하지 않습니다. 정본은 저자의 정의와 이론적 연속성의 기준이며, 그 주장의 외부 타당성을 자동으로 입증하지 않습니다.

## 로컬 검증 도구

Python 3.10 이상 표준 라이브러리만 사용합니다. 별도의 API 키가 필요하지 않습니다.

```sh
python plugins/leehumanities-research/scripts/research_audit.py --help
python plugins/leehumanities-research/scripts/research_audit.py corpus-index --source /path/to/corpus --run-dir /path/to/run
python plugins/leehumanities-research/scripts/research_audit.py evidence-validate --input /path/to/evidence.json --run-dir /path/to/run
python plugins/leehumanities-research/scripts/research_audit.py drift-check --before /path/to/before.md --after /path/to/after.md --protected-terms /path/to/terms.json --run-dir /path/to/run
```

- **corpus-index:** 파일의 위치·종류·해시를 기록합니다. 파일을 읽었다는 학술적 확인이나 문헌의 내용 판정은 하지 않습니다.
- **evidence-validate:** 출처 존재, 실제 접근 범위, 인용 위치와 검토자 기록 등의 형식·일관성을 검사합니다. 초록만 읽은 기록을 원문 전체 검증으로 표시한 경우 등 잘못된 기록을 거부합니다.
- **drift-check:** 두 원고의 보호 용어·수치·인용 표기 변화에 관한 검토 목록을 만듭니다. 의미 보존 여부의 최종 판단은 사람이 합니다.

`PASS`는 **검증 기록이 정해진 조건에 맞는다는 의미**입니다. 논문이 참이라는 인증이 아닙니다. 정확한 입력 형식과 합성 예시는 플러그인의 `tests/fixtures/`와 `scripts/research_audit.py`에서 확인할 수 있습니다.

## 검증과 개발

```sh
python tools/leehumanities/validate_package.py
python -m unittest discover -s tools/leehumanities -p 'test_*.py' -v
python -m unittest discover -s plugins/leehumanities-research/tests -p 'test_*.py' -v
claude plugin validate plugins/leehumanities-research --strict
claude plugin validate .claude-plugin/marketplace.json --strict
```

위 검사는 Linux와 Windows에서 실행했습니다. GitHub Actions 자동 검사를 위한 [워크플로 예제](tools/leehumanities/github-actions.example.yml)도 제공하지만, 이 배포에서는 자동 실행을 활성화하지 않았습니다. GitHub 인증에 워크플로 변경 권한이 있는 경우 예제를 `.github/workflows/leehumanities.yml`에 추가할 수 있습니다. 원본의 다른 워크플로는 이 포크의 검증 절차가 아닙니다.

소프트웨어 검사는 모델을 호출하지 않으므로 검사 통과가 인문학적 해석의 정확도나 실제 심사 성능을 입증하지 않습니다. 배포 검증 기록은 [VALIDATION.leehumanities.md](VALIDATION.leehumanities.md)에 구분해 남깁니다.

실제 역할 호출을 시험할 때 사용할 [합성 원고](plugins/leehumanities-research/tests/fixtures/runtime-manuscript.md)와 [합성 자료 A](plugins/leehumanities-research/tests/fixtures/runtime-source-a.md)도 제공합니다. 이 원고에는 원문과 반대인 직접 인용과 과잉 일반화가 의도적으로 들어 있습니다. 해당 파일을 별도 작업 폴더에 복사한 뒤 `review`에 전달하고 실제 배정한 역할과 근거를 확인하세요. 이 시험은 Claude 로그인이 필요하며 사용량이 발생합니다. 한 합성 사례의 성공을 실제 연구 전반의 정확도로 해석하지 않습니다.

## 배포 범위와 라이선스

원본 ARS 3.24.4를 포크했습니다. 작성자는 Cheng-I Wu이며 원본과 이 배포판은 **CC BY-NC 4.0**의 출처 표시·비상업 조건을 따릅니다. 자세한 관계와 변경 범위는 [UPSTREAM.md](UPSTREAM.md), 설치물 안의 [NOTICE.md](plugins/leehumanities-research/NOTICE.md)에 있습니다.

실행에 쓰는 Claude 구독 한도나 API 비용은 별도입니다. 이 플러그인은 외부 모델 API를 자동으로 호출하지 않습니다. 국문·영문 원고, 철학적 독창성, 원전 해석의 타당성은 연구자의 검토를 거쳐야 합니다.

---

**English:** A Korean humanities adaptation of Academic Research Skills, with four explicitly dispatchable Claude roles, original-edition citation records, Korean/English abstracts and local evidence-record/drift tools. Install `leehumanities-research@leehumanities`. The standalone package is in `plugins/leehumanities-research`; upstream sources remain in the fork for provenance. Mechanical tests do not certify semantic truth or research quality.
