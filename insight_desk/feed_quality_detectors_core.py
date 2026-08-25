from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import StrEnum
import re


_CONTEXT_DEPENDENT_SUMMARY_LEADS = (
    "여기에 ",
    "여기에,",
    "이후 ",
    "이 딜러는 ",
    "이번 ",
    "팬들의 ",
    "그는 ",
    "그가 ",
    "그녀는 ",
    "그녀가 ",
    "이들은 ",
    "이들이 ",
    "가운데 ",
    "가운데,",
)
_CONTEXT_DEPENDENT_SUMMARY_PHRASES = ("이번 상황",)
_GENERIC_CONTEXT_SUBJECT_RE = re.compile(
    r"^(?:(?:이|해당)\s*)?(?:회사|기업|업체)(?:는|은|이|가|\s+측은|\s+측이)(?:\s|$)"
    r"|^(?:양사|양측|(?:두|세|네)\s+(?:회사|기업|업체|기관|조직))"
    r"(?:는|은|이|가)(?:\s|$)"
    r"|^(?:(?:두|세|네)\s+)?(?:투수|선수|타자|팀)(?:는|은|이|가)?(?:\s|$)"
)
_GENERIC_CIVIC_ACTOR_RE = re.compile(
    r"^(?:관할\s+)?(?:지자체|지방자치단체|자치단체|당국|관계\s+당국|관할\s+기관)"
    r"(?:는|은|이|가|,)(?:\s|$)"
)
_REFERENTIAL_EVENT_RE = re.compile(
    r"(?:^|\s)이번\s+(?:승리|패배|경기|장면|계약|발표|결정|조치|상황)"
)
_BARE_ANNIVERSARY_LEAD_RE = re.compile(r"^데뷔\s+\d+\s*주년을\s+맞은\s+가운데(?:\s|$)")
_BARE_RANKING_CUES = ("최고의 루키",)
_BARE_RANKING_CONTEXT_TERMS = (
    "K탑스타",
    "KTOPSTAR",
    "투표",
    "랭킹",
    "차트",
    "부문",
    "시상식",
    "어워드",
    "수상",
)
_DATE_LED_SUBJECTLESS_SPORTS_RESULT_RE = re.compile(
    r"^(?:지난\s+)?\d{1,2}일\s+[^,.]{0,60}?(?:경기|전)에서\s+"
    r"[^,.]{0,60}?\d+\s*(?:타수|이닝|분|경기)\b"
)
_CONTEXT_DEPENDENT_CREATED_CATEGORY_RE = re.compile(
    r"(?:분야|부문)(?:를|을)?\s+(?:신설(?:했|한|한다|됐다|된|된다)?|새로\s+마련)"
)
_ORPHANED_OPENING_CONTENT_LEAD_RE = re.compile(
    r"^(?:개장|개관|출범)\s+(?:첫|후속)\s+콘텐츠로(?:는)?(?:\s|$)"
)
_ORPHANED_CHILD_CONTENT_ROLE_RE = re.compile(
    r"^(?![^.!?。！？]{0,100}(?:에서|의\s+(?:개장|개관|출범)))"
    r"[^.!?。！？]{1,100}?(?:전시|공연|프로그램|행사|작품|영상|콘텐츠)"
    r"(?:은|는|이|가)\s+(?:개장\s+|개관\s+)?(?:첫|후속)\s+콘텐츠로\s+"
    r"(?:마련|선정|공개)"
)
_PARENTLESS_STAGE_LEAD_RE = re.compile(r"^무대(?:에는|에|는)(?:\s|$)")
_GENERIC_STAGE_APPEARANCE_RE = re.compile(
    r"(?:무대\s+출연|무대에\s+출연(?:한다|합니다|할\s+예정이다|할\s+예정입니다))"
    r"[.!?。！？]?$"
)
_PERFORMER_CUES = (
    "가수",
    "그룹",
    "밴드",
    "아티스트",
    "래퍼",
    "보컬",
    "아이돌",
    "K-POP",
    "케이팝",
    "힙합",
)
_NAMED_PERFORMANCE_PARENT_CUES = (
    "콘서트",
    "축제",
    "페스티벌",
    "쇼케이스",
    "시상식",
    "음악제",
)
_REFERENTIAL_REMAINDER_RE = re.compile(
    r"(?:^|[\s,·])(?:나머지|그\s*외|이외의?)\s*\d+\s*"
    r"(?:종목|명|개|곳|팀|기관|기업|업체|회사|제품|콘텐츠|작품|곡|경기)"
    r"(?:은|는|이|가|을|를)?(?:\s|$)"
)
_INTENT_EXPLANATORY_END_RE = re.compile(
    r"(?:겠다는|겠다고\s+한다는)\s+것이다$"
)
_SUBORDINATE_INTENT_CONNECTOR_RE = re.compile(
    r"(?:자|면서|때문에)\s+"
)
_NON_SUBJECT_PARTICLE_ENDINGS = (
    "다는",
    "라는",
    "에서는",
    "로는",
    "에는",
    "과는",
    "와는",
    "까지는",
    "부터는",
)
_CREATED_CATEGORY_PARENT_CUES = (
    "공모전",
    "공모",
    "경진대회",
    "디자인 대전",
    "시상식",
    "프로그램",
    "프로젝트",
    "사업",
    "제도",
    "과정",
    "학과",
    "전형",
    "조직",
    "본부",
    "센터",
)
_MISSING_FINANCIAL_TENOR_RE = re.compile(
    r"(?:미국|한국|일본|중국|독일|영국)\s+년\s+만기\s+(?:국채|채권)"
)
_MISSING_FINANCIAL_VALUE_RE = re.compile(
    r"(?:금리|수익률|환율|가격|지수|비율)(?:이|가|은|는)\s+(?:에|로)\s+"
    r"(?:도달|진입|마감|상승|하락|올랐|내렸)"
)
_MISSING_BLOCK_BOUNDARY_RE = re.compile(
    r"(?:참석|발표|개최|확정|선정|수상|발매|출시|공개)"
    r"(?=(?!(?:자들?|여부|일정|내용|자료|행사)(?:은|는|이|가))"
    r"[가-힣A-Za-z0-9·&-]{2,28}(?:은|는|이|가)\s)"
)
_TRAILING_LIST_FRAGMENT_RE = re.compile(r"[,，;；、]\s*$")
_INCOMPLETE_ADNOMINAL_HEADLINE_RE = re.compile(
    r"(?:이끈|거둔|밝힌|발표한|체결한|개최한|진행한|기록한|수주한|선정된|확정된|"
    r"결정된|출시한|발매한|공개한|상승한|하락한|오른|내린|앞둔|나선|보인|만든|"
    r"올린|늘린|줄인|마련한|추진한|허용한)$"
)
_PREDICATE_LED_CONDITIONAL_HEADLINE_RE = re.compile(
    r"^(?:높아지|낮아지|오르|내리|늘어나|줄어들|증가하|감소하|상승하|하락하|"
    r"커지|작아지|강해지|약해지)면(?:\s|,|$)"
)
_VISIBLE_BYLINE_RE = re.compile(
    r"(?:"
    r"^[\(（\[][^\)）\]]{0,80}(?:기자|특파원|뉴스)[\)）\]]\s*"
    r"|(?:^|[\s,])(?:[가-힣A-Za-z0-9·]+(?:뉴스|일보|신문|방송|통신|TV))\s+"
    r"[가-힣]{2,4}\s+(?:기자|특파원)(?:가|이)?\s+(?:전했다|보도했다)(?:[.!?。！？]|$)"
    r")"
)
_STANDALONE_SOURCE_CREDIT_RE = re.compile(
    r"^[\[\(（]?(?:(?:사진|자료|영상)\s*[:：]\s*)?"
    r"[^.!?。！？]{0,60}?"
    r"(?:사무국|구단|협회|연맹|위원회|공사|재단|은행|청|부|처|뉴스|일보|신문|통신|방송)"
    r"\s+제공[\]\)）]?$"
)
_SUBJECTLESS_FUNDING_MAIN_CLAUSE_RE = re.compile(
    r"(?:^|,\s*)(?:모집액|청약액|수요|자금)(?:을|이|은|는)\s*"
    r"[^.!?。！？]{0,100}?(?:확보|완판|조달)"
    r"[^.!?。！？]{0,40}?(?:성공|확정|마무리|했다)"
)
_GENERIC_FUNDING_HEADLINE_LEADS = (
    "투자 심리",
    "시장 심리",
    "채권 심리",
    "자금 모집",
    "모집액",
    "수요예측",
)
_FUNDING_EVENT_CUES = ("자금 모집", "모집액", "수요예측", "신종자본증권", "회사채")
_FUNDING_RESULT_CUES = ("완판", "조달", "발행", "확보")
_NAMED_ACTOR_AFTER_CONTEXT_RE = re.compile(
    r"(?:속|에도|불구하고)\s+[가-힣A-Za-z0-9·&-]{2,30}(?:은|는|이|가|,)\s*"
)
_MIXED_EXPLANATORY_SUBJECT_RE = re.compile(
    r"[.!?。！？]\s*이는\s+[^.!?。！？]{0,160}?"
    r"(?:현상|영향|결과|배경)(?:으)?로,\s*"
    r"[가-힣A-Za-z0-9·&-]{2,30}(?:은|는|이|가)\s+"
)
_HISTORICAL_DECADE_RE = re.compile(r"(?<!\d)((?:18|19|20)\d{2})년대")
_CURRENT_RESEARCH_OBJECT_CUES = (
    "연구 결과",
    "연구결과",
    "조사 결과",
    "조사결과",
    "분석 결과",
    "분석결과",
    "보고서",
    "논문",
)
_CURRENT_RESEARCH_REPORTING_CUES = (
    "발표했다",
    "공개했다",
    "발간했다",
    "출간했다",
)
_YEAR_RE = re.compile(r"(?<!\d)(20\d{2})년")
_CURRENT_EVENT_CUES = ("올해", "오늘", "현재", "최근")
_PAST_YEAR_BACKGROUND_CUES = ("부터", "이후", "이래")
_PAST_YEAR_MODIFIER_CUES = (
    "설립한",
    "설립된",
    "창업한",
    "창립한",
    "출범한",
)
_KBO_HANWHA_TOPIC = "KBO·한화 이글스"
_HANWHA_SUBJECT_LEAD_RE = re.compile(r"^한화(?:\s+이글스)?(?:는|은|이|가|,|\s)")
_HANWHA_GAMES_PLAYED_COMPARISON_RE = re.compile(
    r"한화(?:\s+이글스)?(?:보다(?:는)?|와\s+마찬가지|\s*대비)"
    r"[^.!?。！？]{0,40}?\d+\s*경기[^.!?。！？]{0,40}?"
    r"(?:덜|적게|많이|더)\s*(?:경기(?:를)?\s*)?치렀"
)
_DISCOURSE_LEADS = ("하지만 ", "그러나 ", "다만 ", "반면 ")
_LEADING_QUARTER_RE = re.compile(
    r"^(?:(지난)\s+)?(?:(20\d{2})년\s*)?([1-4])분기(?:\s|$)"
)
_DAY_ONLY_PAST_RE = re.compile(r"(?:^|[,.]\s*|\s)지난\s+([0-3]?\d)일(?:\s|$)")
_BARE_DAY_SPORTS_EVENT_RE = re.compile(
    r"(?<!\d)([0-3]?\d)일(?!\s*(?:동안|간|뒤|후|째))\s+"
    r"[^.!?。！？]{0,80}?(?:경기|전)에서(?:\s|$)"
)
_BARE_DAY_MATERIAL_EVENT_RE = re.compile(
    r"(?<!\d)([0-3]?\d)일"
    r"(?:\s*(?:과|와|·|,)\s*[0-3]?\d일)?"
    r"(?!\s*(?:동안|간|뒤|후|째))\s+"
    r"[^.!?。！？]{0,120}?"
    r"(?:콘서트|공연|쇼케이스|페스티벌|시상식|행사|발매|출시|공개|발표|체결)"
)
_STALE_DAY_ONLY_EVENT_CUES = (
    "경기",
    "전에서",
    "등판",
    "진행",
    "개최",
    "발표",
    "출시",
    "공개",
    "체결",
    "기록",
    "승리",
    "패배",
)
_NON_EVENT_ANALYTICAL_ENDINGS = (
    "설명하기 어렵다",
    "설명하기 힘들다",
    "것으로 보인다",
    "것으로 보입니다",
    "것으로 풀이된다",
    "것으로 풀이됩니다",
)
_NON_EVENT_ATTENTION_ENDINGS = (
    "관심이 쏠리고 있다",
    "관심이 쏠리고 있습니다",
    "관심이 모이고 있다",
    "관심이 모이고 있습니다",
    "주목을 받고 있다",
    "주목받고 있다",
    "가능성을 주목하고 있다",
    "가능성을 주목하고 있습니다",
)
_NON_EVENT_INFERENCE_ENDINGS = ("셈이다", "셈입니다")
_NON_EVENT_TREND_ENDINGS = (
    "늘고 있다",
    "늘고 있습니다",
    "늘어나고 있다",
    "늘어나고 있습니다",
    "증가하고 있다",
    "증가하고 있습니다",
    "줄고 있다",
    "줄고 있습니다",
    "감소하고 있다",
    "감소하고 있습니다",
)
_NON_EVENT_OPERATIONAL_STATE_ENDINGS = (
    "활용되고 있다",
    "활용되고 있습니다",
    "사용되고 있다",
    "사용되고 있습니다",
    "운영되고 있다",
    "운영되고 있습니다",
    "적용되고 있다",
    "적용되고 있습니다",
)
_NON_EVENT_POSSESSION_STATE_ENDINGS = (
    "보유하고 있다",
    "보유하고 있습니다",
    "보유돼 있다",
    "보유돼 있습니다",
    "보유되어 있다",
    "보유되어 있습니다",
    "갖추고 있다",
    "갖추고 있습니다",
)
_NON_EVENT_AUDIENCE_RESPONSE_CUES = (
    "관람객",
    "시청자",
    "청중",
    "독자",
    "팬",
    "소비자",
    "이용자",
    "참가자",
    "어린이",
    "흥미",
    "호기심",
    "관심",
    "인기",
    "호응",
)
_NON_EVENT_AUDIENCE_FORECAST_ENDINGS = (
    "것으로 전망된다",
    "것으로 전망됩니다",
    "것으로 기대된다",
    "것으로 기대됩니다",
    "것으로 예상된다",
    "것으로 예상됩니다",
)
_QUANTIFIED_TREND_RE = re.compile(
    r"\d[\d,.]*\s*(?:%|％|명|건|개|곳|배|원|달러|경기|승|패|세이브|홀드|이닝)"
)
_DEFINITION_STATEMENT_RE = re.compile(
    r"^(?:[^.!?。！？]{1,80}?)(?:은|는|란)\s+"
    r"[^.!?。！？]{1,180}?(?:뜻한다|의미한다|말한다|뜻입니다|의미입니다)$"
)
_DEFINITION_ROLE_STATEMENT_RE = re.compile(
    r"^[^.!?。！？]{1,80}?(?:은|는|란)\s+"
    r"(?=[^.!?。！？]{1,260}?(?:기준이\s+되는|의미|뜻|개념|용어|사용되는|활용되는))"
    r"[^.!?。！？]{1,260}?(?:역할|기능)(?:을|를)\s+(?:한다|합니다)$"
)
_GENERIC_CLASSIFICATION_STATEMENT_RE = re.compile(
    r"^[^.!?。！？]{1,80}?(?:은|는|란)\s+[^.!?。！？]{1,180}?"
    r"(?:구간|파생상품|지표|상품|자산|제도|방식|개념|용어|수단|도구|특징)"
    r"(?:이다|입니다)$"
)
_GENERIC_USAGE_DEFINITION_RE = re.compile(
    r"^[^.!?。！？]{1,80}?(?:은|는|란)\s+[^.!?。！？]{1,180}?"
    r"(?:지표|수단|도구)(?:로|으로)\s+(?:활용|사용|쓰)된다$"
)
_GENERIC_EVALUATIVE_CLASSIFICATION_RE = re.compile(
    r"^[^.!?。！？]{1,100}?(?:은|는|이|가)\s+[^.!?。！？]{1,200}?"
    r"(?:구간|상품|자산|지표|수단|도구|특징)(?:으)?로\s+"
    r"(?:꼽힌다|평가된다|분류된다|여겨진다|인식된다)$"
)
_ENDURING_REQUIREMENT_RE = re.compile(
    r"(?:계속|여전히|지속적으로)\s+(?:요구|필요)"
    r"(?:(?:된다|됩니다|하다|합니다)|"
    r"(?:된다고|된다는|하다고|하다는)\s+"
    r"(?:설명|분석|평가|진단)(?:했다|됐다|된다))$"
)
_EVALUATIVE_CONDITION_MARKERS = ("해야", "돼야", "되어야")
_EVALUATIVE_CONDITION_ENDINGS = (
    "가능하다고 봤다",
    "필요하다고 봤다",
    "가능하다고 평가했다",
    "필요하다고 평가했다",
    "의미가 있다고 봤다",
)
_DESCRIPTIVE_ATTRIBUTE_CUES = (
    "장르",
    "사운드",
    "스타일",
    "분위기",
    "매력",
    "탑라인",
    "트랙",
    "색채",
    "특징",
)
_DESCRIPTIVE_PREDICATE_CUES = (
    "대비를 이루",
    "은유한다",
    "표현한다",
    "보여준다",
    "담아낸다",
    "결합한",
    "특징이다",
)
_MEDIA_DESCRIPTION_CONTAINER_CUES = (
    "앨범",
    "음반",
    "수록곡",
    "곡들",
    "트랙",
    "EP",
    "싱글",
)
_MEDIA_DESCRIPTION_ATTRIBUTE_CUES = (
    "보컬",
    "랩",
    "사운드",
    "장르",
    "분위기",
    "스타일",
    "색채",
    "가사",
    "멜로디",
    "탑라인",
)
_MEDIA_DESCRIPTION_PREDICATE_CUES = (
    "선보였다",
    "선보이고 있다",
    "담겼다",
    "담겨 있다",
    "들려준다",
    "보여준다",
    "표현한다",
    "구성됐다",
    "특징이다",
)
_LIVE_PERFORMANCE_EVENT_CUES = ("콘서트", "공연", "무대", "쇼케이스", "페스티벌")
_BIOGRAPHICAL_IDENTITY_CUES = (
    "출신",
    "가수이자",
    "배우인",
    "멤버인",
    "소속된",
    "소속돼",
)
_BIOGRAPHICAL_ROLE_CUES = (
    "메인댄서",
    "리드래퍼",
    "서브보컬",
    "리더",
    "보컬",
    "래퍼",
    "역할",
)
_BIOGRAPHICAL_STATE_ENDINGS = (
    "담당하고 있다",
    "담당하고 있습니다",
    "맡고 있다",
    "맡고 있습니다",
    "활동하고 있다",
    "활동하고 있습니다",
    "소속돼 있다",
    "소속돼 있습니다",
    "소속되어 있다",
    "소속되어 있습니다",
)
_BIOGRAPHICAL_COMPOSITION_CUES = (
    "구성된",
    "구성돼",
    "구성되어",
    "인조",
    "멤버로 구성",
)
_BIOGRAPHICAL_REPUTATION_CUES = (
    "글로벌 인기",
    "인기를 얻",
    "대표하는",
    "대표 팀",
    "대표 그룹",
    "자리매김",
)
_EXPLANATORY_STATE_NOUN_CUES = ("원인", "배경", "힘", "요인", "영향", "신호")
_EXPLANATORY_STATE_ENDINGS = (
    "두드러지고 있다",
    "두드러지고 있습니다",
    "두드러진다",
    "작용하고 있다",
    "작용하고 있습니다",
    "작용한다",
    "작용할 수 있다",
    "작용할 수 있습니다",
    "영향을 미치고 있다",
    "영향을 미치고 있습니다",
    "영향을 미친다",
    "영향을 미칠 수 있다",
    "영향을 미칠 수 있습니다",
    "배경이다",
    "배경으로 꼽힌다",
    "요인이다",
    "요인으로 꼽힌다",
    "원인이다",
    "원인으로 꼽힌다",
    "영향으로 해석된다",
    "영향으로 해석됩니다",
    "영향으로 분석된다",
    "영향으로 분석됩니다",
    "배경으로 해석된다",
    "배경으로 해석됩니다",
    "요인으로 해석된다",
    "요인으로 해석됩니다",
    "원인으로 해석된다",
    "원인으로 해석됩니다",
)
_EXPLANATORY_RELATION_CUES = ("필수불가결", "불가분", "밀접", "필요성")
_EXPLANATORY_RELATION_ENDINGS = (
    "연결된다",
    "연결되어 있다",
    "연결돼 있다",
    "관계에 있다",
    "관련이 있다",
    "귀결된다",
)
_ANALYTICAL_DEPENDENCY_RE = re.compile(
    r"(?:에\s+달려\s+있(?:다고|다는)|(?:이|가)\s+관건(?:이라고|이라는))\s*"
    r"(?:분석|평가|진단)(?:했|됐|된|한|이다)"
)
_STRATEGIC_DESIGNATION_RE = re.compile(
    r"(?:사업\s+포트폴리오|성장\s+전략|중장기\s+전략|미래\s+전략|사업\s+비전)"
    r"[^.!?。！？]{0,180}?(?:핵심|주력|중점)\s*(?:사업|분야|축|과제|동력)"
    r"(?:으)?로\s+[^.!?。！？]{1,140}?(?:지목했다|꼽았다)$"
)
_EXPLICIT_DAY_CUE_RE = re.compile(
    r"(?<!\d)(?:(?:20\d{2})년\s*)?(?:(?:1[0-2]|0?[1-9])월\s*)?(?:[0-2]?\d|3[01])일"
)
_ABSTRACT_TRANSFORMATION_ASSERTION_RE = re.compile(
    r"(?:가능성|미래|패러다임|지형|환경|방향성|잠재력)"
    r"[^.!?。！？]{0,120}?"
    r"(?:재정의하|다시\s+정의하|바꾸|변화시키|열어가|확장하)"
    r"고\s+있다고\s+(?:밝혔다|말했다|설명했다|강조했다)$"
)
_EDUCATIONAL_RANGE_RE = re.compile(
    r"(?:소식|사례|개념|용어)부터\s+[^.!?。！？]{1,180}?까지\s+"
    r"[^.!?。！？]{1,120}?(?:접할|볼|확인할|찾아볼)\s+수\s+있다$"
)
_VAGUE_IMPACT_STATE_RE = re.compile(
    r"(?:영향|효과|변화)(?:이|가)\s+(?:나타나고|이어지고|확산되고)\s+있다$"
)
_CONCRETE_EVENT_PREDICATE_CUES = (
    "발매했다",
    "공개했다",
    "개최했다",
    "출시했다",
    "체결했다",
    "수주했다",
    "선정됐다",
    "수상했다",
    "승리했다",
    "발표했다",
    "밝혔다",
    "확정했다",
    "결정했다",
    "도입했다",
    "시행했다",
    "데뷔했다",
    "마감했다",
    "상승했다",
    "하락했다",
    "올랐다",
    "내렸다",
    "동결했다",
    "인상했다",
    "인하했다",
    "기록했다",
    "도달했다",
    "진입했다",
    "투입했다",
    "가동했다",
    "운용을 시작했다",
    "사용을 시작했다",
    "활용을 시작했다",
)
_PUBLICATION_SELF_REFERENCE_RE = re.compile(r"^(?:본지|본보)(?:는|가)\s+")
_PUBLICATION_RETROSPECTIVE_STRONG_CUES = (
    "앞서 ",
    "과거 ",
    "종전 ",
    "이전에 ",
    "지난달 ",
    "지난해 ",
    "지난주 ",
    "지난 분기 ",
    "지난 연도 ",
    "지난 기사에서 ",
)
_PUBLICATION_REPORTING_ENDINGS = (
    "전했다",
    "보도했다",
    "다뤘다",
    "소개했다",
)
_PUBLICATION_PRIOR_REPORT_ENDINGS = (
    "전한 바 있다",
    "보도한 바 있다",
    "다룬 바 있다",
    "소개한 바 있다",
)
_RELATIVE_PAST_PERIOD_RE = re.compile(
    r"(?:지난해|작년|전년도|지난\s+시즌|직전\s+시즌)"
)
_RELATIVE_PAST_EVENT_PERIOD_RE = re.compile(
    r"(?:지난달|지난\s+달|지난주|지난\s+주|지난\s+분기|지난\s+연도)"
)
_PAST_EVENT_BRIDGE_RE = re.compile(r"(?:뒤|후|이후)(?:\s|,)")
_PAST_EVENT_ADNOMINAL_CUES = (
    "발매한",
    "공개한",
    "개최한",
    "출시한",
    "체결한",
    "수주한",
    "선정된",
    "수상한",
    "발표한",
    "확정한",
    "결정한",
    "도입한",
    "시행한",
    "마감한",
    "올린",
    "내린",
    "인상한",
    "인하한",
    "기록한",
    "도달한",
    "진입한",
    "투입한",
    "가동한",
)
_CURRENT_PROPOSITION_CUES = (
    "오늘",
    "현재",
    "오는",
    "이번",
    "가능성",
    "전망",
    "예상",
    "예정",
    "회의",
    "결정",
)
_RELATIVE_PAST_COMPARISON_RE = re.compile(
    r"^(?:(?:1[0-2]|0?[1-9])월(?:\s*(?:[0-2]?\d|3[01])일)?\s*)?"
    r"(?:보다|대비|동기|수준|이후|이래|부터|기록(?:을|보다))"
)
_SPORTS_RECORD_RE = re.compile(
    r"(?:\d+\s*(?:경기|이닝|승|패|세이브|홀드|홈런)|"
    r"평균자책점|타율|마무리(?:\s+보직|\s+투수)?|선발(?:\s+등판)?|등판|우승|패배)"
)
_CONDITIONAL_EVENT_CUES = (
    "발표",
    "밝혔다",
    "결정",
    "도입",
    "시행",
    "공개",
    "추진",
    "합의",
    "체결",
    "승인",
    "확정",
)
_CONDITIONAL_SCENARIO_RE = re.compile(r"\s(?:경우|시)\s")
_CONDITIONAL_CAUSAL_EXPLAINER_RE = re.compile(
    r"(?:으)?면(?:\s|,)\s*[^.!?。！？]{1,240}?"
    r"(?:때문(?:이다|입니다)|이유(?:다|입니다))$"
)
_SENTENCE_TERMINALS = ".!?。！？"


class VisibleStoryIssue(StrEnum):
    CONTEXT_DEPENDENT_HEADLINE = "FEED_QUALITY_CONTEXT_DEPENDENT_HEADLINE"
    CONTEXT_DEPENDENT_SUMMARY = "FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY"
    HEADLINE_SUMMARY_COLLISION = "FEED_QUALITY_HEADLINE_SUMMARY_COLLISION"
    VISIBLE_METADATA = "FEED_QUALITY_VISIBLE_METADATA"
    NON_EVENT_ANALYTICAL_SUMMARY = "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY"
    CONDITIONAL_ANALYTICAL_SUMMARY = "FEED_QUALITY_CONDITIONAL_ANALYTICAL_SUMMARY"
    MALFORMED_VISIBLE_TEXT = "FEED_QUALITY_MALFORMED_VISIBLE_TEXT"
    MIXED_EVENT_SUMMARY = "FEED_QUALITY_MIXED_EVENT_SUMMARY"
    STALE_DATED_CONTEXT = "FEED_QUALITY_STALE_DATED_CONTEXT"
    TOPIC_BINDING = "FEED_QUALITY_TOPIC_BINDING"


def _bare_ranking_fragment(value: str) -> bool:
    normalized = " ".join(value.split())
    has_bare_ranking = (
        any(cue in normalized for cue in _BARE_RANKING_CUES)
        or re.search(r"\d+\s*주\s*연속\s*1위", normalized) is not None
    )
    if not has_bare_ranking:
        return False
    folded = normalized.casefold()
    return not any(term.casefold() in folded for term in _BARE_RANKING_CONTEXT_TERMS)


def _context_dependent_text(value: str) -> bool:
    normalized = " ".join(value.split())
    if any(normalized.startswith(cue) for cue in _CONTEXT_DEPENDENT_SUMMARY_LEADS):
        return True
    if any(phrase in normalized for phrase in _CONTEXT_DEPENDENT_SUMMARY_PHRASES):
        return True
    if _GENERIC_CONTEXT_SUBJECT_RE.search(normalized) is not None:
        return True
    if generic_civic_actor_text(normalized):
        return True
    if _REFERENTIAL_EVENT_RE.search(normalized) is not None:
        return True
    if _BARE_ANNIVERSARY_LEAD_RE.search(normalized) is not None:
        return True
    if _DATE_LED_SUBJECTLESS_SPORTS_RESULT_RE.search(normalized) is not None:
        return True
    if (
        _CONTEXT_DEPENDENT_CREATED_CATEGORY_RE.search(normalized) is not None
        and not any(cue in normalized for cue in _CREATED_CATEGORY_PARENT_CUES)
    ):
        return True
    if orphaned_parent_content_role_text(normalized):
        return True
    if parentless_performer_lineup_text(normalized):
        return True
    if referential_remainder_text(normalized):
        return True
    if _subjectless_funding_result(normalized):
        return True
    return _bare_ranking_fragment(normalized)


def orphaned_parent_content_role_text(value: str) -> bool:
    normalized = " ".join(value.split())
    return (
        _ORPHANED_OPENING_CONTENT_LEAD_RE.search(normalized) is not None
        or _ORPHANED_CHILD_CONTENT_ROLE_RE.search(normalized) is not None
    )


def parentless_performer_lineup_text(value: str) -> bool:
    normalized = " ".join(value.split())
    if not any(cue in normalized for cue in _PERFORMER_CUES):
        return False
    if any(cue in normalized for cue in _NAMED_PERFORMANCE_PARENT_CUES):
        return False
    return (
        _PARENTLESS_STAGE_LEAD_RE.search(normalized) is not None
        or _GENERIC_STAGE_APPEARANCE_RE.search(normalized) is not None
    )


def _has_explicit_clause_subject(value: str) -> bool:
    for token in value.split():
        normalized_token = token.strip(" \\t,·()[]{}'\"")
        if not normalized_token.endswith(("은", "는", "이", "가")):
            continue
        if normalized_token.endswith(_NON_SUBJECT_PARTICLE_ENDINGS):
            continue
        return True
    return False


def _subjectless_intentional_remainder_text(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(_SENTENCE_TERMINALS).rstrip()
    if _INTENT_EXPLANATORY_END_RE.search(normalized) is None:
        return False
    connectors = tuple(_SUBORDINATE_INTENT_CONNECTOR_RE.finditer(normalized))
    main_clause = normalized[connectors[-1].end() :] if connectors else normalized
    return not _has_explicit_clause_subject(main_clause)


def referential_remainder_text(value: str) -> bool:
    normalized = " ".join(value.split())
    return (
        _REFERENTIAL_REMAINDER_RE.search(normalized) is not None
        or _subjectless_intentional_remainder_text(normalized)
    )


def generic_civic_actor_text(value: str) -> bool:
    return _GENERIC_CIVIC_ACTOR_RE.search(" ".join(value.split())) is not None


def _subjectless_funding_result(normalized: str) -> bool:
    if _SUBJECTLESS_FUNDING_MAIN_CLAUSE_RE.search(normalized) is not None:
        return True
    return (
        any(normalized.startswith(cue) for cue in _GENERIC_FUNDING_HEADLINE_LEADS)
        and any(cue in normalized for cue in _FUNDING_EVENT_CUES)
        and any(cue in normalized for cue in _FUNDING_RESULT_CUES)
        and _NAMED_ACTOR_AFTER_CONTEXT_RE.search(normalized) is None
    )


def malformed_visible_text(value: str) -> bool:
    normalized = " ".join(value.split())
    return (
        _MISSING_FINANCIAL_TENOR_RE.search(normalized) is not None
        or _MISSING_FINANCIAL_VALUE_RE.search(normalized) is not None
        or _MISSING_BLOCK_BOUNDARY_RE.search(normalized) is not None
        or _TRAILING_LIST_FRAGMENT_RE.search(normalized) is not None
    )


def context_dependent_headline(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(_SENTENCE_TERMINALS).rstrip()
    return (
        _context_dependent_text(normalized)
        or _INCOMPLETE_ADNOMINAL_HEADLINE_RE.search(normalized) is not None
        or _PREDICATE_LED_CONDITIONAL_HEADLINE_RE.search(normalized) is not None
        or _TRAILING_LIST_FRAGMENT_RE.search(normalized) is not None
    )


def context_dependent_summary(value: str) -> bool:
    return _context_dependent_text(value)


def metadata_or_caption_text(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(_SENTENCE_TERMINALS).rstrip()
    return (
        _VISIBLE_BYLINE_RE.search(normalized) is not None
        or _STANDALONE_SOURCE_CREDIT_RE.search(normalized) is not None
    )


def visible_metadata_text(value: str) -> bool:
    return metadata_or_caption_text(value)


def _relative_past_bridge_to_current_text(normalized: str) -> bool:
    for match in _RELATIVE_PAST_EVENT_PERIOD_RE.finditer(normalized):
        following = normalized[match.end() :].lstrip()
        bridge = _PAST_EVENT_BRIDGE_RE.search(following)
        if bridge is None:
            continue
        past_clause = following[: bridge.start()]
        current_clause = following[bridge.end() :]
        if (
            any(cue in past_clause for cue in _PAST_EVENT_ADNOMINAL_CUES)
            and any(cue in current_clause for cue in _CURRENT_PROPOSITION_CUES)
        ):
            return True
    return False


def mixed_event_summary(value: str) -> bool:
    normalized = " ".join(value.split())
    return (
        _MIXED_EXPLANATORY_SUBJECT_RE.search(normalized) is not None
        or _relative_past_bridge_to_current_text(normalized)
    )


def _historical_background_text(
    value: str,
    *,
    now: datetime | None = None,
) -> bool:
    normalized = " ".join(value.split())
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if f"{reference.year}년" in normalized or any(cue in normalized for cue in _CURRENT_EVENT_CUES):
        return False
    if (
        any(cue in normalized for cue in _CURRENT_RESEARCH_OBJECT_CUES)
        and any(cue in normalized for cue in _CURRENT_RESEARCH_REPORTING_CUES)
    ):
        return False
    return any(
        int(match.group(1)) <= reference.year - 10
        for match in _HISTORICAL_DECADE_RE.finditer(normalized)
    )


def stale_explicit_past_event_text(
    value: str,
    *,
    now: datetime | None = None,
) -> bool:
    normalized = " ".join(value.split())
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if _historical_background_text(normalized, now=reference):
        return True
    if f"{reference.year}년" in normalized or any(cue in normalized for cue in _CURRENT_EVENT_CUES):
        return False
    for match in _YEAR_RE.finditer(normalized):
        if int(match.group(1)) >= reference.year:
            continue
        following = normalized[match.end() : match.end() + 16].lstrip()
        if any(following.startswith(cue) for cue in _PAST_YEAR_BACKGROUND_CUES):
            continue
        if any(following.startswith(cue) for cue in _PAST_YEAR_MODIFIER_CUES):
            continue
        prefix = normalized[: match.start()]
        if any(cue in prefix for cue in _CONCRETE_EVENT_PREDICATE_CUES):
            continue
        return True
    return False


def stale_relative_past_event_text(value: str) -> bool:
    normalized = " ".join(value.split())
    if any(cue in normalized for cue in _CURRENT_EVENT_CUES):
        return False
    if _SPORTS_RECORD_RE.search(normalized) is None:
        return False
    for match in _RELATIVE_PAST_PERIOD_RE.finditer(normalized):
        following = normalized[match.end() :].lstrip()
        if _RELATIVE_PAST_COMPARISON_RE.match(following) is not None:
            continue
        if any(cue in following for cue in _CONCRETE_EVENT_PREDICATE_CUES):
            return True
    return False


def stale_relative_period_event_text(value: str) -> bool:
    normalized = " ".join(value.split())
    if _relative_past_bridge_to_current_text(normalized):
        return True
    if any(cue in normalized for cue in _CURRENT_EVENT_CUES):
        return False
    for match in _RELATIVE_PAST_EVENT_PERIOD_RE.finditer(normalized):
        following = normalized[match.end() :].lstrip()
        if _RELATIVE_PAST_COMPARISON_RE.match(following) is not None:
            continue
        if any(cue in following for cue in _CONCRETE_EVENT_PREDICATE_CUES):
            return True
    return False


def kbo_hanwha_comparison_only(
    *,
    topic: str,
    headline: str,
    summary: str,
) -> bool:
    if topic != _KBO_HANWHA_TOPIC:
        return False
    normalized_headline = " ".join(headline.split())
    normalized_summary = " ".join(summary.split())
    if _HANWHA_SUBJECT_LEAD_RE.search(normalized_headline) is not None:
        return False
    if _HANWHA_SUBJECT_LEAD_RE.search(normalized_summary) is not None:
        return False
    return _HANWHA_GAMES_PLAYED_COMPARISON_RE.search(
        f"{normalized_headline}. {normalized_summary}"
    ) is not None


def _visible_identity(value: str) -> str:
    normalized = " ".join(value.split()).rstrip(_SENTENCE_TERMINALS).rstrip()
    for cue in _DISCOURSE_LEADS:
        if normalized.startswith(cue):
            normalized = normalized[len(cue) :].lstrip()
            break
    return normalized.casefold()


def headline_summary_collision(*, headline: str, summary: str) -> bool:
    return bool(_visible_identity(headline)) and _visible_identity(headline) == _visible_identity(summary)


def stale_day_only_context(value: str, *, now: datetime | None = None) -> bool:
    normalized = " ".join(value.split())
    if any(cue in normalized for cue in ("오늘", "현재", "최근")):
        return False
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    matches = (
        (match, True, False) for match in _DAY_ONLY_PAST_RE.finditer(normalized)
    )
    sports_matches = (
        (match, False, True) for match in _BARE_DAY_SPORTS_EVENT_RE.finditer(normalized)
    )
    material_matches = (
        (match, False, True) for match in _BARE_DAY_MATERIAL_EVENT_RE.finditer(normalized)
    )
    seen_days: set[tuple[int, int]] = set()
    for match, explicit_past, event_match in (*matches, *sports_matches, *material_matches):
        day = int(match.group(1))
        day_key = (match.start(1), day)
        if day_key in seen_days:
            continue
        seen_days.add(day_key)
        candidates: list[datetime] = []
        for month_offset in (0, -1):
            month_index = reference.year * 12 + reference.month - 1 + month_offset
            year, zero_based_month = divmod(month_index, 12)
            try:
                candidate = datetime(year, zero_based_month + 1, day, tzinfo=timezone.utc)
            except ValueError:
                continue
            candidates.append(candidate)
        if not candidates:
            continue
        if explicit_past:
            past_candidates = [
                candidate for candidate in candidates if candidate <= reference + timedelta(hours=6)
            ]
            if not past_candidates:
                continue
            candidate = max(past_candidates)
        else:
            candidate = min(candidates, key=lambda item: abs(item - reference))
            if candidate > reference + timedelta(hours=6):
                continue
        if reference - candidate <= timedelta(hours=72):
            continue
        event_surface = normalized[match.start() : match.end() + 100]
        if event_match or any(cue in event_surface for cue in _STALE_DAY_ONLY_EVENT_CUES):
            return True
    return False


def stale_quarter_context(value: str, *, now: datetime | None = None) -> bool:
    normalized = " ".join(value.split())
    match = _LEADING_QUARTER_RE.search(normalized)
    if match is None:
        return False
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    past_text, year_text, quarter_text = match.groups()
    quarter = int(quarter_text)
    current_quarter = (reference.month - 1) // 3 + 1
    if year_text is not None:
        year = int(year_text)
    elif quarter > current_quarter or (past_text is not None and quarter >= current_quarter):
        year = reference.year - 1
    else:
        year = reference.year
    current_ordinal = reference.year * 4 + current_quarter
    quarter_ordinal = year * 4 + quarter
    return current_ordinal - quarter_ordinal >= 2


def _publication_retrospective_text(normalized: str) -> bool:
    for sentence in re.split(r"[.!?。！？]\s*", normalized):
        sentence = sentence.strip()
        if _PUBLICATION_SELF_REFERENCE_RE.search(sentence) is None:
            continue
        if sentence.endswith(_PUBLICATION_PRIOR_REPORT_ENDINGS):
            return True
        if not sentence.endswith(_PUBLICATION_REPORTING_ENDINGS):
            continue
        if any(cue in sentence for cue in _PUBLICATION_RETROSPECTIVE_STRONG_CUES):
            return True
        if "최근 " in sentence and "이미 " in sentence:
            return True
    return False


def _descriptive_media_profile_text(normalized: str) -> bool:
    if any(cue in normalized for cue in _CURRENT_EVENT_CUES):
        return False
    if any(cue in normalized for cue in _CONCRETE_EVENT_PREDICATE_CUES):
        return False
    if (
        any(cue in normalized for cue in _MEDIA_DESCRIPTION_CONTAINER_CUES)
        and any(cue in normalized for cue in _MEDIA_DESCRIPTION_ATTRIBUTE_CUES)
        and any(cue in normalized for cue in _MEDIA_DESCRIPTION_PREDICATE_CUES)
        and not any(cue in normalized for cue in _LIVE_PERFORMANCE_EVENT_CUES)
    ):
        return True
    if (
        any(cue in normalized for cue in _BIOGRAPHICAL_COMPOSITION_CUES)
        and any(cue in normalized for cue in _BIOGRAPHICAL_REPUTATION_CUES)
    ):
        return True
    return (
        any(cue in normalized for cue in _BIOGRAPHICAL_IDENTITY_CUES)
        and any(cue in normalized for cue in _BIOGRAPHICAL_ROLE_CUES)
        and normalized.endswith(_BIOGRAPHICAL_STATE_ENDINGS)
    )


def non_event_analytical_text(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(_SENTENCE_TERMINALS).rstrip()
    if metadata_or_caption_text(normalized):
        return True
    if normalized.endswith(_NON_EVENT_ANALYTICAL_ENDINGS):
        return True
    if normalized.endswith(_NON_EVENT_ATTENTION_ENDINGS):
        return True
    if _publication_retrospective_text(normalized):
        return True
    if _historical_background_text(normalized):
        return True
    if _descriptive_media_profile_text(normalized):
        return True
    if _DEFINITION_STATEMENT_RE.search(normalized) is not None:
        return not any(cue in normalized for cue in _CONCRETE_EVENT_PREDICATE_CUES)
    if (
        _DEFINITION_ROLE_STATEMENT_RE.search(normalized) is not None
        or _GENERIC_CLASSIFICATION_STATEMENT_RE.search(normalized) is not None
        or _GENERIC_USAGE_DEFINITION_RE.search(normalized) is not None
        or _GENERIC_EVALUATIVE_CLASSIFICATION_RE.search(normalized) is not None
    ):
        return not any(cue in normalized for cue in _CONCRETE_EVENT_PREDICATE_CUES)
    if (
        _ENDURING_REQUIREMENT_RE.search(normalized) is not None
        and not any(cue in normalized for cue in _CONCRETE_EVENT_PREDICATE_CUES)
    ):
        return True
    if normalized.endswith(_NON_EVENT_TREND_ENDINGS):
        trailing_sentence = re.split(r"[.!?。！？]\s*", normalized)[-1]
        if _QUANTIFIED_TREND_RE.search(trailing_sentence) is None:
            return True
    if (
        normalized.endswith(_NON_EVENT_OPERATIONAL_STATE_ENDINGS)
        and not any(cue in normalized for cue in _CONCRETE_EVENT_PREDICATE_CUES)
    ):
        return True
    if (
        normalized.endswith(_NON_EVENT_POSSESSION_STATE_ENDINGS)
        and not any(cue in normalized for cue in _CONCRETE_EVENT_PREDICATE_CUES)
    ):
        return True
    if (
        any(cue in normalized for cue in _NON_EVENT_AUDIENCE_RESPONSE_CUES)
        and normalized.endswith(_NON_EVENT_AUDIENCE_FORECAST_ENDINGS)
        and not any(cue in normalized for cue in _CONCRETE_EVENT_PREDICATE_CUES)
    ):
        return True
    if (
        normalized.endswith(_NON_EVENT_INFERENCE_ENDINGS)
        and not any(cue in normalized for cue in _CONCRETE_EVENT_PREDICATE_CUES)
    ):
        return True
    if (
        any(marker in normalized for marker in _EVALUATIVE_CONDITION_MARKERS)
        and normalized.endswith(_EVALUATIVE_CONDITION_ENDINGS)
    ):
        return True
    if (
        any(cue in normalized for cue in _EXPLANATORY_STATE_NOUN_CUES)
        and normalized.endswith(_EXPLANATORY_STATE_ENDINGS)
        and not any(cue in normalized for cue in _CONCRETE_EVENT_PREDICATE_CUES)
    ):
        return True
    if (
        any(cue in normalized for cue in _EXPLANATORY_RELATION_CUES)
        and normalized.endswith(_EXPLANATORY_RELATION_ENDINGS)
        and not any(cue in normalized for cue in _CONCRETE_EVENT_PREDICATE_CUES)
    ):
        return True
    if (
        _ANALYTICAL_DEPENDENCY_RE.search(normalized) is not None
        and not any(cue in normalized for cue in _CONCRETE_EVENT_PREDICATE_CUES)
    ):
        return True
    if (
        _STRATEGIC_DESIGNATION_RE.search(normalized) is not None
        and _EXPLICIT_DAY_CUE_RE.search(normalized) is None
        and not any(cue in normalized for cue in _CURRENT_EVENT_CUES)
        and not any(cue in normalized for cue in _CONCRETE_EVENT_PREDICATE_CUES)
    ):
        return True
    if (
        _ABSTRACT_TRANSFORMATION_ASSERTION_RE.search(normalized) is not None
        and _QUANTIFIED_TREND_RE.search(normalized) is None
    ):
        return True
    if (
        _EDUCATIONAL_RANGE_RE.search(normalized) is not None
        and not any(cue in normalized for cue in _CONCRETE_EVENT_PREDICATE_CUES)
    ):
        return True
    if (
        _VAGUE_IMPACT_STATE_RE.search(normalized) is not None
        and _QUANTIFIED_TREND_RE.search(normalized) is None
        and not any(cue in normalized for cue in _CONCRETE_EVENT_PREDICATE_CUES)
    ):
        return True
    return (
        any(cue in normalized for cue in _DESCRIPTIVE_ATTRIBUTE_CUES)
        and any(cue in normalized for cue in _DESCRIPTIVE_PREDICATE_CUES)
        and not any(cue in normalized for cue in _CONCRETE_EVENT_PREDICATE_CUES)
    )


def conditional_analytical_text(value: str) -> bool:
    normalized = " ".join(value.split())
    has_reporting_event = any(cue in normalized for cue in _CONDITIONAL_EVENT_CUES)
    if "더라도" in normalized and "이어야" in normalized:
        return not has_reporting_event
    terminal_stripped = normalized.rstrip(_SENTENCE_TERMINALS).rstrip()
    if _CONDITIONAL_CAUSAL_EXPLAINER_RE.search(terminal_stripped) is not None:
        return not has_reporting_event
    if _CONDITIONAL_SCENARIO_RE.search(normalized) is None:
        return False
    return not has_reporting_event
