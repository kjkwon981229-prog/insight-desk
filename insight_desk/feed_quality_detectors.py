from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re

# Keep the accumulated low-level detector implementation byte-for-byte intact.
# This public façade adds only measured live-surface regressions; admission policy
# composition remains exclusively in story_admission.py.
from insight_desk._feed_quality_detectors_impl import *  # noqa: F401,F403
from insight_desk import _feed_quality_detectors_impl as _impl
from insight_desk.feed_quality_detectors_core import (
    _CONCRETE_EVENT_PREDICATE_CUES as _CORE_CONCRETE_EVENT_PREDICATE_CUES,
)


# A deictic event mention is standalone only when its visible text has already
# introduced an event antecedent. Model the discourse relation, not one particle
# surface: 이번/해당/이 + a generic event class and its case particle are the
# same unresolved referent family.  The visible text must name that event before
# referring back to it; an ordinal ("17회째") is not an identity antecedent.
_DEICTIC_EVENT_REFERENCE_RE = re.compile(
    r"(?<![가-힣A-Za-z0-9])(?:이번|해당|이)\s+"
    r"(?P<head>행사|대회|박람회|축제|공연|콘서트|캠페인|시상식|포럼|토론회)"
    r"(?:은|는|이|가|을|를|의|에|에서|에는|로|으로)?(?=\s|$)"
)
_SUBJECTLESS_MARKET_HEADLINE_RE = re.compile(
    r"^장\s+(?:초반|중반|후반)\s+\d+(?:\.\d+)?%\s+(?:넘게\s+)?"
    r"(?:떨어지|오르|하락|상승)"
)
_UNSCOPED_COMPARATIVE_MOVEMENT_HEADLINE_RE = re.compile(
    r"^(?:하락폭|상승폭|낙폭|오름폭|내림폭)(?:은|는|이|가)\s+"
    r"(?:축소|확대)(?:됐다|되었다|됐습니다|되었습니다)$"
)
_MALFORMED_KBO_LEAGUE_YEAR_RE = re.compile(
    r"(?<!\d)\d{3}\s+신한(?:은행)?\s+(?:SOL(?:\s+Bank)?\s+)?KBO리그"
)
_GENERIC_LABOR_MANAGEMENT_RE = re.compile(r"^노사(?:는|가|의|,|\s)")
_REFERENTIAL_REPORT_LEAD_RE = re.compile(r"^(?:같은\s+)?보도(?:는|가)(?:\s|$)")
_GENERIC_COMPANY_LEAD_RE = re.compile(r"^(?:(?:이|해당|그)\s+)?회사(?:는|가|의)(?:\s|$)")
_BARE_ROLE_LEAD_RE = re.compile(
    r"^(?:책임자|관계자|당국자|담당자|실무자|전문가)(?:들)?(?:은|는|이|가)(?=\s|$)"
)
_SURNAME_ONLY_LEGISLATOR_RE = re.compile(
    r"^[가-힣]\s+(?:국회의원|의원)(?:은|는|이|가)?(?=[,，]?\s|$)"
)
_GENERIC_FACILITY_ACTOR_RE = re.compile(
    r"^(?:국내|현지|지역|해외)\s+"
    r"[가-힣A-Za-z0-9·&()/_+-]{2,24}(?:공장|사업장|생산기지|연구소|센터)"
    r"(?:은|는|이|가)(?=\s|$)"
)
_SUBJECTLESS_STOCK_TO_COMPANY_RE = re.compile(
    r"^주가(?:는|가)?[^.!?。！？,，]{0,100}(?:가운데|상황에서|속에서)?\s*[,，]\s*"
    r"(?:(?:이|해당|그)\s+)?회사(?:는|가|의)(?:\s|$)"
)
_ORPHANED_TEST_REFERENCE_RE = re.compile(r"(?:^|\s)해당\s+테스트(?:에|에서|를|는|가|의|\s)")
_INTERPRETIVE_BACKGROUND_END_RE = re.compile(
    r"(?:상징적으로\s+)?(?:드러낸|보여주는)\s+(?:표현|사례|대목)(?:이다|입니다)$"
)
_GENERIC_MARKET_COGNITION_RE = re.compile(
    r"^(?:시장(?:은|이|에서는)|증시(?:는|가|에서는)|"
    r"투자자(?:들)?(?:은|는|이|가)|시장\s+참여자(?:들)?(?:은|는|이|가))\s+"
    r"[^.!?。！？]{0,260}?"
    r"(?:보고\s+있다|보고\s+있습니다|평가한다|평가하고\s+있다|평가하고\s+있습니다|"
    r"판단한다|판단하고\s+있다|해석한다|해석하고\s+있다|"
    r"주목하고\s+있다|주목하고\s+있습니다|기대하고\s+있다|기대하고\s+있습니다|"
    r"관심(?:을)?\s+(?:쏟고|집중하고)\s+있다|관심(?:을)?\s+(?:쏟고|집중하고)\s+있습니다)$"
)
_GENERIC_MARKET_ATTENTION_STATE_RE = re.compile(
    r"^(?:시장|증시|투자자(?:들)?|시장\s+참여자(?:들)?)의\s+관심(?:은|이)\s+"
    r"[^.!?。！？]{0,260}?"
    r"(?:향하고|쏠리고|모이고|집중되고|쏠려|모여)\s+있(?:다|습니다)$"
)
_ROLLING_MARKET_STATE_RE = re.compile(
    r"^(?:코스피|코스닥|원달러\s*환율|원·달러\s*환율|환율|증시|주가지수)"
    r"(?:은|는|이|가)\s+[^.!?。！？]{0,180}?"
    r"(?:등락을\s+반복|오르내리)[^.!?。！？]{0,100}?"
    r"(?:방향을\s+잡|방향성을\s+찾)[^.!?。！？]{0,30}?못하고\s+있다$"
)
_ABSTRACT_EMERGENCE_ATTENTION_RE = re.compile(
    r"(?:모델|방식|전략|흐름|움직임)(?:이|가)\s+"
    r"(?:새로\s+)?(?:등장|나타나|확산)(?:해|하며|하면서|하고|했다|하고\s+있)[^.!?。！？]{0,140}?"
    r"(?:이목|관심|주목)(?:을|이)?\s*(?:모으|끌)"
)
_CONDITIONAL_EXPECTED_BENEFIT_RE = re.compile(
    r"(?:하면|할\s+경우|한다면)\s*[^.!?。！？]{0,180}?"
    r"(?:도움(?:이|을)?\s+될|기여할|활성화(?:에|를)?\s+도움|효과(?:가|를)?\s+(?:있|낼))"
    r"[^.!?。！？]{0,100}?(?:것으로\s+)?"
    r"(?:기대됐|기대된다|기대됩니다|전망됐|전망된다|전망됩니다)"
)
_ROLLING_SPORTS_FORM_RE = re.compile(
    r"최근\s+\d+\s*경기(?:에서|는|동안)?[^.!?。！？]{0,70}?\d+\s*승\s*\d+\s*패"
)
_ROLLING_SPORTS_FORM_END_RE = re.compile(
    r"(?:기록했다|기록하였다|기록했습니다|그쳤다|그쳤습니다)$"
)
_AI_PREVIEW_PUBLISHER_NOTICE_RE = re.compile(
    r"^\*?\s*위\s+내용은\s+생성형\s+AI로\s+예측한\s+경기\s+분석(?:\s|$)",
    flags=re.IGNORECASE,
)
_COMPONENT_FEATURE_SUBJECT_RE = re.compile(
    r"^(?:[가-힣A-Za-z0-9·-]+\s+){0,5}"
    r"(?:팝업\s+전시|전시|부스|체험존|전시관|체험\s+공간|프로그램)"
    r"(?:은|는|이|가)(?=\s)"
)
_COMPONENT_FEATURE_END_RE = re.compile(
    r"(?:제공한다|제공합니다|지원한다|지원합니다|운영한다|운영합니다|"
    r"구성된다|구성됩니다)$"
)
_COMPONENT_CURRENT_EVENT_RE = re.compile(
    r"(?:개막|개최|오픈|문을\s+열|출시|공개|발표|도입|신설|시작|선보였|선보인다)"
)
_PARENTLESS_EXHIBITION_FEATURE_RE = re.compile(
    r"^(?:K-POP\s+)?(?:[A-Za-z가-힣0-9·-]+\s+){0,3}"
    r"(?:팝업\s+전시|체험관|전시관|체험존)에서\s+"
    r"(?:관람객|방문객)(?:은|는|이|가)\s+[^.!?。！？]{1,220}?"
    r"(?:체험|제작|이용)[^.!?。！？]{0,100}?"
    r"(?:할\s+수\s+있|이용할\s+수\s+있)[^.!?。！？]{0,140}?"
    r"(?:안내|다국어)[^.!?。！？]{0,80}?제공된다$"
)
_LEADING_TIMESTAMP_CHROME_RE = re.compile(
    r"^\s*[-–—]?\s*(?:입력|기사입력|등록|수정|업데이트)\s+"
    r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}(?:\s+\d{1,2}:\d{2})?(?=\s|$)",
    flags=re.IGNORECASE,
)
_SQUARE_BRACKET_BYLINE_RE = re.compile(
    r"\[[^\]\n=]{1,50}=[^\]\n]{1,50}\s+(?:기자|특파원)\]"
)
_LEADING_SECTION_GLYPH_RE = re.compile(r"^[◆◇](?=\S)")
_LEADING_SOURCE_BULLET_RE = re.compile(r"^(?:[-–—•])\s+")
_STATIC_COMPANY_CAPABILITY_RE = re.compile(
    r"(?:\d[\d,.]*(?:만|천|백)?\s*점\s+이상|\d[\d,.]*\s*개(?:의)?)"
    r"\s*(?:의\s+)?(?:제품|의료기기|품목)"
    r"[^.!?。！？]{0,90}?(?:취급|보유|운영)"
    r"[^.!?。！？]{0,50}?(?:한다|하고\s+있|덧붙였)"
)
_STATIC_CAPABILITY_CURRENT_EVENT_RE = re.compile(
    r"(?:\d{1,2}일|계약|체결|출시|공개|발표|도입|신규|시작|확대했|추가했)"
)
_STATIC_PRODUCT_DEFINITION_RE = re.compile(
    r"^[가-힣A-Za-z0-9·&()/_+.-]{1,30}"
    r"(?:\s+[가-힣A-Za-z0-9·&()/_+.-]{1,30}){0,5}(?:은|는|이|가)\s+"
    r"[^.!?。！？]{1,240}?(?:솔루션|플랫폼|서비스|제품)(?:이다|입니다)$"
)
_STATIC_COMPANY_IDENTITY_RE = re.compile(
    r"^[가-힣A-Za-z0-9·&()/_+.-]{2,40}(?:은|는|이|가)\s+"
    r"[^.!?。！？]{1,260}?(?:제조|개발|공급|운영|제공)하는\s+기업(?:이다|입니다)$"
)
_SURVEY_METHOD_ONLY_RE = re.compile(
    r"(?:국가|지역)(?:들)?(?:을|를)\s+[^.!?。！？]{0,100}?"
    r"선정(?:하여|해)\s+[^.!?。！？]{0,100}?(?:조사|설문)(?:을|를)?\s+(?:진행|실시)했다$"
)
_ONGOING_STRATEGY_DESCRIPTION_RE = re.compile(
    r"^[가-힣A-Za-z0-9·&()/_+.-]{2,50}(?:은|는|이|가)\s+"
    r"[^.!?。！？]{1,240}?(?:전략|체계)(?:을)?\s+(?:제시|추진|전개|구축)하고\s+있다$"
)
_ALBUM_NARRATIVE_SYNOPSIS_RE = re.compile(
    r"(?:이야기|서사|메시지)(?:가|를|은|는)?"
    r"[^.!?。！？]{0,80}?(?:앨범|음반)(?:에|에는)"
    r"[^.!?。！？]{0,30}?(?:담겼|담았|담아냈)"
)
_ALBUM_CURRENT_EVENT_RE = re.compile(
    r"(?:\d{1,2}일|발매|출시|공개|컴백|활동\s+시작|계획을\s+공개|계획을\s+발표)"
)
_MULTI_VOTE_COUNT_RE = re.compile(r"(?<!\d)\d[\d,]*\s*표")
_MULTI_CATEGORY_TOP_RESULT_RE = re.compile(
    r"\d+\s*개\s*부문\s*TOP\s*\d+\s*에\s*들었다$",
    flags=re.IGNORECASE,
)
_NAMED_HEADLINE_LEAD_RE = re.compile(r"^[가-힣A-Za-z0-9·&()/_+-]{2,40},\s")
_EXPLICIT_VISIBLE_SUBJECT_RE = re.compile(
    r"(?:^|\s)[가-힣A-Za-z0-9·&()/_+-]{2,40}(?:은|는|이|가)(?=\s)"
)
_GENERIC_ALBUM_TRACKLIST_HEADLINE_RE = re.compile(
    r"^(?:앨범|음반)\s+(?:수록곡|트랙(?:리스트)?)\s+\d+\s*곡(?:\s+(?:공개|수록))?$"
)
_BARE_ALBUM_TRACKLIST_SUMMARY_RE = re.compile(
    r"\d+\s*곡(?:이|은|을)?\s+(?:앨범|음반)에\s+수록(?:됐|되었|됐다|되었다|돼)"
)
_EXPLICIT_RESEARCH_RELEASE_DATE_RE = re.compile(
    r"(?:(?P<year>20\d{2})년\s*)?(?:지난\s+)?"
    r"(?P<month>1[0-2]|0?[1-9])월\s*(?P<day>3[01]|[12]\d|0?[1-9])일\s+"
    r"[^.!?。！？]{0,80}?(?:공개한|발표한|발간한|출간한)\s+"
    r"(?:보고서|조사|분석|연구|자료)"
)
_KBO_TEAM_RE = re.compile(
    r"(?:한화(?:\s+이글스)?|SSG(?:\s*랜더스)?|KIA(?:\s*타이거즈)?|LG(?:\s*트윈스)?|"
    r"두산(?:\s*베어스)?|롯데(?:\s*자이언츠)?|삼성(?:\s*라이온즈)?|KT(?:\s*위즈)?|"
    r"NC(?:\s*다이노스)?|키움(?:\s*히어로즈)?)",
    flags=re.IGNORECASE,
)
_KBO_GENERIC_RESULT_RE = re.compile(
    r"(?:경기\s*(?:에서\s*)?(?:패배|승리)|경기를\s+(?:내주었|내줬|내주었다|이겼|승리했))"
)
_KBO_SCORE_RE = re.compile(r"(?<!\d)\d{1,2}\s*(?:대|[-:])\s*\d{1,2}(?!\d)")
_KBO_DAY_RE = re.compile(r"(?<!\d)(?:[0-3]?\d)일(?!\s*(?:간|동안|후|뒤|째))")
_MATCHLESS_HANWHA_STARTER_PREVIEW_RE = re.compile(
    r"^한화(?:\s+이글스)?\s+[가-힣A-Za-z·-]+(?:\s+[가-힣A-Za-z·-]+){0,2}\s+선발\s+등판$"
)

# Discourse references are handled as a syntactic family instead of extending one
# live-specific noun blacklist. Measure-like heads still form a semantic class because
# a bare "이/그/해당 + measure" requires a visible value or prior lexical antecedent.
_DEICTIC_MEASURE_REFERENCE_RE = re.compile(
    r"(?<![가-힣A-Za-z0-9])(?:이|그|해당)\s+"
    r"(?P<head>[가-힣A-Za-z0-9·_-]{1,20})"
    r"(?:은|는|이|가|을|를|로|에|에서|의)(?=\s|$)"
)
_MEASURE_REFERENCE_HEAD_RE = re.compile(
    r"(?:수치|비율|지표|지수|값|수준|규모|금액|가격|점수|증가율|성장률|감소율|점유율|율|률)$"
)
_VISIBLE_QUANTITY_RE = re.compile(
    r"(?<!\d)\d[\d,.]*(?:\.\d+)?\s*(?:%|％|배|원|달러|명|건|개|회|점|위)?"
)
_DEICTIC_ANALYTICAL_SOURCE_RE = re.compile(
    r"(?<![가-힣A-Za-z0-9])(?:이번|해당|이|그|이날)\s+"
    r"(?P<head>모델|자료|보고서|분석|조사|통계|예측|전망)"
    r"(?:은|는|이|가|을|를|의|에|에서|로|으로)?(?=\s|[,.!?。！？]|$)"
)
_CONNECTIVE_LED_HEADLINE_RE = re.compile(r"^[가-힣]{2,30}(?:으)?면서(?=\s)")
_ANONYMOUS_ABSTRACT_CHANGE_RE = re.compile(
    r"(?:기업(?:의)?|업계(?:의)?|산업(?:의)?|시장(?:의)?|보안\s+환경|운영\s+방식|인프라)"
    r"[^.!?。！？]{0,180}?"
    r"(?:급변|빠르게\s+바뀌|변화하|달라지|재편되)"
    r"[^.!?。！？]{0,30}?(?:고\s+있다|고\s+있습니다)$"
)
_REPORTING_PREDICATE_END_RE = re.compile(
    r"(?:분석|평가|진단|전망|예상|관측)(?:했다|하였다)$"
)
_PARENTLESS_TASK_LEAD_RE = re.compile(
    r"^(?:지정|선정)\s+과제(?:는|가|를|은|의)?(?=\s|$)"
)
_SUBJECTLESS_CAUSAL_REMAINDER_RE = re.compile(
    r"^[^.!?。！？,，]{1,80}?(?:을|를)\s+"
    r"(?:끌어올리|끌어내리|높이|낮추|늘리|줄이)"
    r"[^.!?。！？]{0,60}?(?:고|며)[,，]?\s+"
    r"[^.!?。！？]{0,140}?부담(?:을|이)?\s+(?:주|준|준다|된다)"
)
_ORPHANED_REPORTING_ADNOMINAL_HEADLINE_RE = re.compile(
    r"^(?:발표|공개|발간|공표|집계|작성|조사)한\s+"
    r"[^.!?。！？]{1,180}?(?:통계|자료|보고서|조사|분석)"
    r"(?:에\s+따르면|에서)(?:[,，]?\s|$)"
)
_GENERIC_RATE_HEADLINE_RE = re.compile(r"^(?:상품\s+)?금리(?:는|가)?(?=\s)")
_SCOPED_RATE_SUMMARY_RE = re.compile(
    r"(?:주담대|주택담보대출|신용대출|일반신용대출|기업대출|가계대출|예금은행)"
    r"(?:\s+(?:중|고정형|변동형|일반신용대출|신용대출|상품)){0,4}\s+"
    r"(?:상품\s+)?금리"
)
_UNATTRIBUTED_PASSIVE_INTERPRETATION_RE = re.compile(
    r"(?:반영된\s+것으로\s+)?(?:해석|풀이)된다$"
)
_ATTRIBUTION_CUE_RE = re.compile(
    r"(?:에\s+따르면|보고서(?:는|에서|에\s+따르면)|분석(?:은|에\s+따르면)|"
    r"연구진(?:은|이)|증권사(?:는|가)|은행(?:은|이))"
)
_MEDIA_SYNOPSIS_RE = re.compile(
    r"(?:작품|영화|애니메이션)(?:은|는)?[^.!?。！？]{0,220}?"
    r"(?:배경으로|배경에)[^.!?。！？]{0,180}?"
    r"(?:만남|이별|성장|우정|이야기|서사)[^.!?。！？]{0,100}?"
    r"(?:그린다|다룬다|담는다)$"
)
_ATMOSPHERE_ONLY_SCENE_RE = re.compile(
    r"^(?=[^.!?。！？]{0,300}?(?:K-POP|콘서트|공연장))"
    r"[^.!?。！？]{0,180}?(?:강당|현장|객석)(?:은|는|이|가)\s+"
    r"[^.!?。！？]{0,220}?(?:(?:방불케[^.!?。！？]{0,160}?)|(?:같은\s+[^.!?。！？]{0,80}?))"
    r"(?:열기|분위기)(?:로\s+가득\s+찼|를\s+(?:보였|연출했))(?:다|습니다)$"
)
_SAME_DAY_PAST_CUE_RE = re.compile(
    r"지난\s+(?:(?P<month>1[0-2]|0?[1-9])월\s*)?"
    r"(?P<day>3[01]|[12]\d|0?[1-9])일"
)
_RATIONALE_ONLY_PRIMARY_RE = re.compile(
    r"^[^.!?。！？]{1,140}?(?:강화|확대|개선|고도화)에\s+나선\s+것은\s+"
    r"[^.!?。！？]{1,220}?때문이다$"
)
_ORPHANED_REPORTED_TREND_RE = re.compile(
    r"^[^.!?。！？]{1,100}?(?:늘어남에\s+따라|증가함에\s+따라|확대됨에\s+따라|"
    r"늘면서|증가하면서|확대되면서)\s+"
    r"[^.!?。！？]{1,220}?다고\s+전했다$"
)
_ONGOING_BUSINESS_EXPANSION_RE = re.compile(
    r"^[가-힣A-Za-z0-9·&()/_+-]{2,40}(?:은|는|이|가)\s+"
    r"[^.!?。！？]{1,180}?분야로\s+사업\s+영역을\s+확장하고\s+있다$"
)
_BARE_NUMERIC_MOVEMENT_HEADLINE_RE = re.compile(
    r"^\d[\d,.]*\s*(?:원|달러|%|％|포인트)?(?:으로|로)\s+출발한\s+뒤\s+"
)
_ACTORLESS_MARKET_SESSION_HEADLINE_RE = re.compile(
    r"^(?:전장|전일|직전\s+거래일)\s+대비\s+.{1,140}?"
    r"(?:출발한\s+뒤|출발해).{1,140}?(?:장(?:을)?\s+)?마감했다$"
)
_HEADLESS_ONGOING_ACTION_HEADLINE_RE = re.compile(
    r"^이제는\s+[^.!?。！？]{1,80}?"
    r"(?:내리고|줄이고|올리고|늘리고)\s+있(?:습니다|다)$"
)
_INSTITUTIONAL_SUMMARY_ACTOR_RE = re.compile(
    r"(?:저축은행|시중은행|은행|증권사|기업|업체)(?:들)?(?:은|는|이|가)"
)
_RETROSPECTIVE_CONTINUITY_SUMMARY_RE = re.compile(
    r"(?:선보이며|소개하며|공개하며)[^.!?。！？]{0,140}?"
    r"팬들과\s+소통(?:을\s+)?(?:(?:이어왔|해\s*왔)(?:다|습니다)|했(?:다|습니다))$"
)
_RELEASE_PROMOTION_HEADLINE_RE = re.compile(
    r"(?:영상|브이로그|뮤직비디오|비하인드|콘텐츠)[^.!?。！？]{0,80}?공개$"
)
_ANONYMOUS_GENERALIZATION_END_RE = re.compile(
    r"(?:가능성(?:이|은)\s+(?:커지|높아지|확대되|증가하)고\s+있다|"
    r"(?:에만\s+)?머물지\s+않는다)$"
)
_ANONYMOUS_SECTOR_STATE_RE = re.compile(
    r"(?:^|[,，]\s*)(?:관련\s+)?(?:산업계|업계|기업들?|업체들?)"
    r"(?:은|는|이|가)\s+[^.!?。！？]{1,180}?"
    r"(?:구체화|강화|확대|본격화|가속)(?:하고|되고|시키고)\s+있다$"
)
_MONTH_DAY_RE = re.compile(
    r"(?<!\d)(?P<month>1[0-2]|0?[1-9])월\s*"
    r"(?P<day>3[01]|[12]\d|0?[1-9])일"
)
_RELATIVE_PAST_MONTH_RE = re.compile(r"지난\s*(?:달|(?:1[0-2]|[1-9])월)")
_RELATIVE_MONTH_COMPARISON_LEAD_RE = re.compile(
    r"^(?:보다|대비|수준|이후|이래|과\s+비교)"
)
_PAST_STATEMENT_PREDICATE_RE = re.compile(
    r"(?:제시|강조|언급|설명|발언)(?:했다|하였다)|말했다"
)
_CURRENT_DAY_RE_TEMPLATE = r"(?<!\d)(?:(?:{month})월\s*)?{day}일"
_DATE_LED_HEADLINE_RE = re.compile(
    r"^(?:지난\s+)?(?:(?:20\d{2})년\s*)?"
    r"(?:(?:1[0-2]|0?[1-9])월\s*)?(?:3[01]|[12]\d|0?[1-9])일"
    r"(?:\([^)]{1,20}\))?(?:\s+오(?:전|후)\s+\d{1,2}시(?:\s*\d{1,2}분)?)?(?=\s)"
)
_DATE_LED_DEPENDENT_EVENT_LEAD_RE = re.compile(
    r"^(?:(?:발표|공개|발간|집계|조사|작성|공표)한(?:\s|$)|"
    r"(?:각종|온라인|오프라인)\s+[^.!?。！？]{1,60}?(?:에서|를\s+통해)(?=\s))"
)
_LEADING_STARTING_PITCHER_ROLE_RE = re.compile(r"^선발\s+투수(?:는|은|이|가)(?=\s)")
_LEADING_SUBJECT_PARTICLES = ("은", "는", "이", "가")

_DATE_LED_SPORTS_STAT_RE = re.compile(
    r"^(?:지난\s+)?\d{1,2}일\s+"
    r"(?P<context>.{0,220}?)"
    r"(?:경기|전)(?:에|에서)\s+"
    r".{0,100}?\d+(?:[⅛¼⅜½⅝¾⅞⅓⅔])?\s*(?:타수|이닝|경기)\b"
)
_EXPLICIT_POST_DATE_SUBJECT_RE = re.compile(
    r"(?:^|\s)(?P<subject>[가-힣A-Za-z·_-]{2,24})(?:은|는|이|가)(?=\s)"
)

_RELATIVE_PAST_SPORTS_PERIOD_RE = re.compile(
    r"(?:지난해|작년|전년도|지난\s+시즌|직전\s+시즌)"
)
_RELATIVE_PAST_COMPARISON_RE = re.compile(
    r"(?:지난해|작년|전년도|지난\s+시즌|직전\s+시즌)\s*(?:보다|대비|이후|이래)"
)
_SPORTS_PERFORMANCE_RE = re.compile(
    r"(?:\d[\d,.]*\s*(?:경기|이닝|승|패|세이브|홀드|홈런|안타|타점)|평균자책점)"
)
_SPORTS_PERFORMANCE_PREDICATE_RE = re.compile(
    r"(?:기록(?:했|하|해|하며|했고|하였다|해냈)|활약(?:했|하|하며)|이끌(?:었|며)|등판(?:했|하|해))"
)
_SENTENCE_SPLIT_RE = re.compile(r"[.!?。！？]\s*")
_UNATTRIBUTED_EVALUATIVE_STATE_ENDINGS = (
    "꼽힌다",
    "꼽힙니다",
    "꼽히고 있다",
    "꼽히고 있습니다",
    "거론된다",
    "거론됩니다",
    "거론되고 있다",
    "거론되고 있습니다",
    "지목된다",
    "지목됩니다",
    "지목되고 있다",
    "지목되고 있습니다",
)


def _orphaned_referential_event(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    for match in _DEICTIC_EVENT_REFERENCE_RE.finditer(normalized):
        head = match.group("head")
        prefix = normalized[: match.start()].rstrip(" ,:;·")
        if not prefix:
            return True
        antecedent = re.compile(
            rf"(?<![가-힣A-Za-z0-9]){re.escape(head)}"
            r"(?:에서|에는|으로|은|는|이|가|을|를|의|에|로)?"
            r"(?=\s|[,.!?。！？]|$)"
        )
        if antecedent.search(prefix) is not None:
            continue
        return True
    return False


def _orphaned_visible_actor(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return (
        _GENERIC_LABOR_MANAGEMENT_RE.search(normalized) is not None
        or _REFERENTIAL_REPORT_LEAD_RE.search(normalized) is not None
        or _GENERIC_COMPANY_LEAD_RE.search(normalized) is not None
        or _BARE_ROLE_LEAD_RE.search(normalized) is not None
        or _SURNAME_ONLY_LEGISLATOR_RE.search(normalized) is not None
        or _SUBJECTLESS_STOCK_TO_COMPANY_RE.search(normalized) is not None
        or _GENERIC_FACILITY_ACTOR_RE.search(normalized) is not None
    )


def _orphaned_test_reference(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    match = _ORPHANED_TEST_REFERENCE_RE.search(normalized)
    if match is None:
        return False
    prefix = normalized[: match.start()].rstrip(" ,:;·")
    return re.search(r"(?:테스트|시험|벤치마크|평가)", prefix, flags=re.IGNORECASE) is None


def _orphaned_measure_reference(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    for match in _DEICTIC_MEASURE_REFERENCE_RE.finditer(normalized):
        head = match.group("head")
        if _MEASURE_REFERENCE_HEAD_RE.search(head) is None:
            continue
        prefix = normalized[: match.start()].rstrip(" ,:;·")
        if not prefix:
            return True
        if re.search(re.escape(head), prefix, flags=re.IGNORECASE) is not None:
            continue
        if _VISIBLE_QUANTITY_RE.search(prefix) is not None:
            continue
        return True
    return False


def _orphaned_analytical_source_reference(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    for match in _DEICTIC_ANALYTICAL_SOURCE_RE.finditer(normalized):
        head = match.group("head")
        prefix = normalized[: match.start()].rstrip(" ,:;·")
        if not prefix:
            return True
        if re.search(re.escape(head), prefix, flags=re.IGNORECASE) is None:
            return True
    return False


def _primary_sentence(value: str) -> str:
    normalized = " ".join(value.split()).strip()
    return re.split(r"(?<!\d)[.!?。！？](?!\d)\s*", normalized, maxsplit=1)[0].strip()


def _contains_concrete_event_predicate(value: str) -> bool:
    return any(cue in value for cue in _CORE_CONCRETE_EVENT_PREDICATE_CUES)


def _has_current_event_anchor(value: str, *, now: datetime) -> bool:
    normalized = " ".join(value.split()).strip()
    for cue in ("오늘", "현재"):
        position = normalized.find(cue)
        if position >= 0 and _contains_concrete_event_predicate(normalized[position:]):
            return True
    current_day = re.compile(
        _CURRENT_DAY_RE_TEMPLATE.format(month=now.month, day=now.day)
    )
    return any(
        _contains_concrete_event_predicate(normalized[match.end() :])
        for match in current_day.finditer(normalized)
    )


def _stale_month_day_event(value: str, *, now: datetime | None = None) -> bool:
    primary = _primary_sentence(value)
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if _has_current_event_anchor(primary, now=reference):
        return False
    for match in _MONTH_DAY_RE.finditer(primary):
        try:
            candidate = datetime(
                reference.year,
                int(match.group("month")),
                int(match.group("day")),
                tzinfo=timezone.utc,
            )
        except ValueError:
            continue
        if candidate > reference + timedelta(hours=6):
            continue
        if reference - candidate <= timedelta(hours=72):
            continue
        if _contains_concrete_event_predicate(primary[match.end() :]):
            return True
    return False


def _same_day_past_cue(value: str, *, now: datetime | None = None) -> bool:
    normalized = " ".join(value.split()).strip()
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    for match in _SAME_DAY_PAST_CUE_RE.finditer(normalized):
        month_text = match.group("month")
        month = int(month_text) if month_text is not None else reference.month
        day = int(match.group("day"))
        if month == reference.month and day == reference.day:
            return True
    return False


def _stale_relative_month_event(value: str, *, now: datetime | None = None) -> bool:
    primary = _primary_sentence(value)
    match = _RELATIVE_PAST_MONTH_RE.search(primary)
    if match is None:
        return False
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if _has_current_event_anchor(primary, now=reference):
        return False
    following = primary[match.end() :].lstrip()
    if _RELATIVE_MONTH_COMPARISON_LEAD_RE.search(following) is not None:
        return False
    return (
        _contains_concrete_event_predicate(following)
        or _PAST_STATEMENT_PREDICATE_RE.search(following) is not None
    )


def _leading_summary_subject_surface(value: str) -> str | None:
    normalized = " ".join(value.split()).strip()
    for raw in normalized.split()[:8]:
        token = raw.strip(" \t,·()[]{}'\"“”‘’")
        if not token:
            continue
        for particle in _LEADING_SUBJECT_PARTICLES:
            if token.endswith(particle) and len(token) > len(particle):
                return token[: -len(particle)]
    return None


def _has_leading_summary_subject(value: str) -> bool:
    return _leading_summary_subject_surface(value) is not None


def _headline_drops_metric_scope(*, headline: str, summary: str) -> bool:
    normalized_headline = " ".join(headline.split()).strip()
    normalized_summary = " ".join(summary.split()).strip()
    return (
        _GENERIC_RATE_HEADLINE_RE.search(normalized_headline) is not None
        and _SCOPED_RATE_SUMMARY_RE.search(normalized_summary) is not None
    )


def _headline_drops_bare_numeric_metric(*, headline: str, summary: str) -> bool:
    normalized_headline = " ".join(headline.split()).strip()
    normalized_summary = " ".join(summary.split()).strip()
    if _BARE_NUMERIC_MOVEMENT_HEADLINE_RE.search(normalized_headline) is None:
        return False
    metric_subject = _leading_summary_subject_surface(normalized_summary)
    return metric_subject is not None and metric_subject.casefold() not in normalized_headline.casefold()


def _headline_drops_market_session_actor(*, headline: str, summary: str) -> bool:
    normalized_headline = " ".join(headline.split()).rstrip(".!?。！？").rstrip()
    normalized_summary = " ".join(summary.split()).strip()
    if _ACTORLESS_MARKET_SESSION_HEADLINE_RE.search(normalized_headline) is None:
        return False
    metric_subject = _leading_summary_subject_surface(normalized_summary)
    if metric_subject is None or not re.search(r"(?:코스피|코스닥)(?:지수)?$", metric_subject):
        return False
    return metric_subject.casefold() not in normalized_headline.casefold()


def _headline_drops_ordinary_action_actor(*, headline: str, summary: str) -> bool:
    normalized_headline = " ".join(headline.split()).strip()
    normalized_summary = " ".join(summary.split()).strip()
    return (
        _HEADLESS_ONGOING_ACTION_HEADLINE_RE.search(normalized_headline) is not None
        and _INSTITUTIONAL_SUMMARY_ACTOR_RE.search(normalized_summary) is not None
    )


def _headline_promotes_retrospective_continuity(*, headline: str, summary: str) -> bool:
    normalized_headline = " ".join(headline.split()).rstrip(".!?。！？").rstrip()
    normalized_summary = " ".join(summary.split()).rstrip(".!?。！？").rstrip()
    if re.search(r"(?<!\d)\d{1,2}일", normalized_summary) is not None:
        return False
    return (
        _RELEASE_PROMOTION_HEADLINE_RE.search(normalized_headline) is not None
        and _RETROSPECTIVE_CONTINUITY_SUMMARY_RE.search(normalized_summary) is not None
    )


def headline_drops_summary_actor(*, headline: str, summary: str) -> bool:
    normalized_headline = " ".join(headline.split()).strip()
    normalized_summary = " ".join(summary.split()).strip()
    if _LEADING_STARTING_PITCHER_ROLE_RE.search(normalized_summary) is not None:
        return "선발" not in normalized_headline and "투수" not in normalized_headline
    if _headline_drops_metric_scope(headline=normalized_headline, summary=normalized_summary):
        return True
    if _headline_drops_bare_numeric_metric(headline=normalized_headline, summary=normalized_summary):
        return True
    if _headline_drops_market_session_actor(headline=normalized_headline, summary=normalized_summary):
        return True
    if _headline_drops_ordinary_action_actor(headline=normalized_headline, summary=normalized_summary):
        return True
    if _headline_promotes_retrospective_continuity(
        headline=normalized_headline,
        summary=normalized_summary,
    ):
        return True
    reporting_actor = _leading_summary_subject_surface(summary)
    if reporting_actor is not None and _REPORTING_PREDICATE_END_RE.search(normalized_headline):
        return reporting_actor.casefold() not in normalized_headline.casefold()
    date_lead = _DATE_LED_HEADLINE_RE.search(normalized_headline)
    if date_lead is None:
        return False
    if reporting_actor is None:
        return False
    remainder = normalized_headline[date_lead.end() :].lstrip()
    return _DATE_LED_DEPENDENT_EVENT_LEAD_RE.search(remainder) is not None


def _date_led_subjectless_sports_stat(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    match = _DATE_LED_SPORTS_STAT_RE.search(normalized)
    if match is None:
        return False
    return _EXPLICIT_POST_DATE_SUBJECT_RE.search(match.group("context")) is None


def _unidentified_kbo_result(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    if _KBO_GENERIC_RESULT_RE.search(normalized) is None:
        return False
    teams = {match.group(0).casefold() for match in _KBO_TEAM_RE.finditer(normalized)}
    if len(teams) != 1:
        return False
    return _KBO_SCORE_RE.search(normalized) is None and _KBO_DAY_RE.search(normalized) is None


def _unattributed_passive_interpretation(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    if _UNATTRIBUTED_PASSIVE_INTERPRETATION_RE.search(normalized) is None:
        return False
    return _ATTRIBUTION_CUE_RE.search(normalized) is None


def _media_synopsis(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    return _MEDIA_SYNOPSIS_RE.search(normalized) is not None


def _publisher_ai_preview_notice(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return _AI_PREVIEW_PUBLISHER_NOTICE_RE.search(normalized) is not None


def _component_feature_state(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    primary = _SENTENCE_SPLIT_RE.split(normalized, maxsplit=1)[0].strip()
    if not primary:
        return False
    if _PARENTLESS_EXHIBITION_FEATURE_RE.search(primary) is not None:
        return True
    if _COMPONENT_FEATURE_SUBJECT_RE.search(primary) is None:
        return False
    if _COMPONENT_CURRENT_EVENT_RE.search(primary) is not None:
        return False
    return _COMPONENT_FEATURE_END_RE.search(primary) is not None


def _visible_extraction_chrome(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return (
        _LEADING_TIMESTAMP_CHROME_RE.search(normalized) is not None
        or _SQUARE_BRACKET_BYLINE_RE.search(normalized) is not None
        or _LEADING_SECTION_GLYPH_RE.search(normalized) is not None
        or _LEADING_SOURCE_BULLET_RE.search(normalized) is not None
    )


def _static_company_capability(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    primary = _SENTENCE_SPLIT_RE.split(normalized, maxsplit=1)[0].strip()
    if not primary or _STATIC_COMPANY_CAPABILITY_RE.search(primary) is None:
        return False
    return _STATIC_CAPABILITY_CURRENT_EVENT_RE.search(primary) is None


def _static_product_definition(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    primary = _SENTENCE_SPLIT_RE.split(normalized, maxsplit=1)[0].strip()
    if not primary or _STATIC_PRODUCT_DEFINITION_RE.search(primary) is None:
        return False
    return _STATIC_CAPABILITY_CURRENT_EVENT_RE.search(primary) is None


def _context_free_album_synopsis(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    primary = _SENTENCE_SPLIT_RE.split(normalized, maxsplit=1)[0].strip()
    if not primary or _ALBUM_NARRATIVE_SYNOPSIS_RE.search(primary) is None:
        return False
    return _ALBUM_CURRENT_EVENT_RE.search(primary) is None


def _actorless_multi_vote_ranking(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    if len(_MULTI_VOTE_COUNT_RE.findall(normalized)) < 2:
        return False
    if _MULTI_CATEGORY_TOP_RESULT_RE.search(normalized) is None:
        return False
    first_vote = _MULTI_VOTE_COUNT_RE.search(normalized)
    if first_vote is None:
        return False
    prefix = normalized[: first_vote.start()].strip()
    if _NAMED_HEADLINE_LEAD_RE.search(normalized) is not None:
        return False
    return _EXPLICIT_VISIBLE_SUBJECT_RE.search(prefix) is None


def _unidentified_album_tracklist(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    if _GENERIC_ALBUM_TRACKLIST_HEADLINE_RE.search(normalized) is not None:
        return True
    if not normalized.startswith(("‘", "'", "“", '"')):
        return False
    return _BARE_ALBUM_TRACKLIST_SUMMARY_RE.search(normalized) is not None


def _stale_explicit_research_release(
    value: str,
    *,
    now: datetime | None = None,
) -> bool:
    normalized = " ".join(value.split()).strip()
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    for match in _EXPLICIT_RESEARCH_RELEASE_DATE_RE.finditer(normalized):
        year_text = match.group("year")
        year = int(year_text) if year_text is not None else reference.year
        month = int(match.group("month"))
        day = int(match.group("day"))
        try:
            candidate = datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            continue
        if year_text is None and candidate > reference + timedelta(hours=6):
            try:
                candidate = candidate.replace(year=year - 1)
            except ValueError:
                continue
        if candidate > reference + timedelta(hours=6):
            continue
        if reference - candidate > timedelta(hours=72):
            return True
    return False


def visible_metadata_text(value: str) -> bool:
    return (
        _impl.visible_metadata_text(value)
        or _publisher_ai_preview_notice(value)
        or _visible_extraction_chrome(value)
    )


def publisher_notice_boilerplate(value: str) -> bool:
    return _impl.publisher_notice_boilerplate(value) or _publisher_ai_preview_notice(value)


def context_dependent_headline(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return (
        _impl.context_dependent_headline(normalized)
        or _orphaned_referential_event(normalized)
        or _orphaned_visible_actor(normalized)
        or _orphaned_test_reference(normalized)
        or _orphaned_measure_reference(normalized)
        or _orphaned_analytical_source_reference(normalized)
        or _date_led_subjectless_sports_stat(normalized)
        or _unidentified_kbo_result(normalized)
        or _actorless_multi_vote_ranking(normalized)
        or _unidentified_album_tracklist(normalized)
        or _MATCHLESS_HANWHA_STARTER_PREVIEW_RE.search(normalized.rstrip(".!?。！？").rstrip()) is not None
        or _PARENTLESS_TASK_LEAD_RE.search(normalized) is not None
        or _SUBJECTLESS_CAUSAL_REMAINDER_RE.search(normalized) is not None
        or _CONNECTIVE_LED_HEADLINE_RE.search(normalized) is not None
        or _SUBJECTLESS_MARKET_HEADLINE_RE.search(normalized) is not None
        or _UNSCOPED_COMPARATIVE_MOVEMENT_HEADLINE_RE.search(normalized) is not None
        or _ORPHANED_REPORTING_ADNOMINAL_HEADLINE_RE.search(normalized) is not None
    )


def context_dependent_summary(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return (
        _impl.context_dependent_summary(normalized)
        or _orphaned_referential_event(normalized)
        or _orphaned_visible_actor(normalized)
        or _orphaned_test_reference(normalized)
        or _orphaned_measure_reference(normalized)
        or _orphaned_analytical_source_reference(normalized)
        or _unidentified_kbo_result(normalized)
        or _unidentified_album_tracklist(normalized)
        or _PARENTLESS_TASK_LEAD_RE.search(normalized) is not None
        or _SUBJECTLESS_CAUSAL_REMAINDER_RE.search(normalized) is not None
        or _ORPHANED_REPORTED_TREND_RE.search(normalized.rstrip(".!?。！？").rstrip()) is not None
    )


def stale_explicit_past_event_text(
    value: str,
    *,
    now: datetime | None = None,
) -> bool:
    return (
        _impl.stale_explicit_past_event_text(value, now=now)
        or _stale_explicit_research_release(value, now=now)
        or _stale_month_day_event(value, now=now)
        or _same_day_past_cue(value, now=now)
    )


def stale_relative_past_event_text(value: str) -> bool:
    if _impl.stale_relative_past_event_text(value):
        return True
    normalized = " ".join(value.split()).strip()
    primary = _SENTENCE_SPLIT_RE.split(normalized, maxsplit=1)[0].strip()
    if not primary or _RELATIVE_PAST_SPORTS_PERIOD_RE.search(primary) is None:
        return False
    if _RELATIVE_PAST_COMPARISON_RE.search(primary) is not None:
        return False
    return (
        _SPORTS_PERFORMANCE_RE.search(primary) is not None
        and _SPORTS_PERFORMANCE_PREDICATE_RE.search(primary) is not None
    )


def stale_relative_period_event_text(
    value: str,
    *,
    now: datetime | None = None,
) -> bool:
    return _impl.stale_relative_period_event_text(value) or _stale_relative_month_event(
        value,
        now=now,
    )


def non_event_analytical_text(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    primary = _SENTENCE_SPLIT_RE.split(normalized, maxsplit=1)[0].strip()
    rolling_form_only = (
        _ROLLING_SPORTS_FORM_RE.search(primary) is not None
        and _ROLLING_SPORTS_FORM_END_RE.search(primary) is not None
    )
    return (
        _impl.non_event_analytical_text(normalized)
        or _INTERPRETIVE_BACKGROUND_END_RE.search(normalized) is not None
        or normalized.endswith(_UNATTRIBUTED_EVALUATIVE_STATE_ENDINGS)
        or _unattributed_passive_interpretation(primary)
        or _GENERIC_MARKET_COGNITION_RE.search(normalized) is not None
        or _GENERIC_MARKET_ATTENTION_STATE_RE.search(normalized) is not None
        or _ROLLING_MARKET_STATE_RE.search(primary) is not None
        or _ABSTRACT_EMERGENCE_ATTENTION_RE.search(normalized) is not None
        or _CONDITIONAL_EXPECTED_BENEFIT_RE.search(primary) is not None
        or _ANONYMOUS_GENERALIZATION_END_RE.search(primary) is not None
        or _ANONYMOUS_SECTOR_STATE_RE.search(primary) is not None
        or _ANONYMOUS_ABSTRACT_CHANGE_RE.search(primary) is not None
        or _RATIONALE_ONLY_PRIMARY_RE.search(primary) is not None
        or _ONGOING_BUSINESS_EXPANSION_RE.search(primary) is not None
        or _SURVEY_METHOD_ONLY_RE.search(primary) is not None
        or _ONGOING_STRATEGY_DESCRIPTION_RE.search(primary) is not None
        or _media_synopsis(primary)
        or _ATMOSPHERE_ONLY_SCENE_RE.search(primary) is not None
        or rolling_form_only
        or _component_feature_state(primary)
        or _static_company_capability(primary)
        or _static_product_definition(primary)
        or _STATIC_COMPANY_IDENTITY_RE.search(primary) is not None
        or _context_free_album_synopsis(primary)
    )


def malformed_visible_text(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return (
        _impl.malformed_visible_text(normalized)
        or _MALFORMED_KBO_LEAGUE_YEAR_RE.search(normalized) is not None
        or normalized.endswith("·")
    )