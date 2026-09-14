import unittest

from insight_desk.acquisition.runtime import strip_document_publisher_prefix


class DocumentPublisherBoundaryTests(unittest.TestCase):
    def test_only_document_identified_publisher_label_is_removed(self):
        proposition = "김제시는 공무원시험준비반에서 최종합격자를 배출했다."
        html = '<meta property="og:site_name" content="새전북신문">'
        self.assertEqual(strip_document_publisher_prefix("[새전북신문] " + proposition, html), proposition)
        for label in ("[잠정]", "[다른 매체]", "[새전북신문에 따르면]"):
            text = label + " " + proposition
            self.assertEqual(strip_document_publisher_prefix(text, html), text)
        text = "[새전북신문] " + proposition
        self.assertEqual(strip_document_publisher_prefix(text, ""), text)
        conflicting = html + '<meta property="og:site_name" content="다른 매체">'
        self.assertEqual(strip_document_publisher_prefix(text, conflicting), text)

    def test_repeated_exact_title_allows_label_only_on_immediate_lead(self):
        title = "현대硏, 올해 성장률 3.5%로 상향…내년 2.4% 전망"
        proposition = "반도체 경기 호황에 힘입어 올해 한국 경제가 3.5% 성장할 것이라는 전망이 나왔다."
        html = (
            f'<meta property="og:title" content="{title}">'
            '<meta property="og:site_name" content="파이낸셜뉴스">'
        )
        body = f"{title}\n\n[파이낸셜뉴스] {proposition}\n후속 설명이다."

        self.assertEqual(
            strip_document_publisher_prefix(body, html),
            f"{title}\n\n{proposition}\n후속 설명이다.",
        )

        unrelated_lead = f"다른 도입 문장이다.\n[파이낸셜뉴스] {proposition}"
        self.assertEqual(strip_document_publisher_prefix(unrelated_lead, html), unrelated_lead)

        later_label = f"{title}\n실제 첫 문장이다.\n[파이낸셜뉴스] {proposition}"
        self.assertEqual(strip_document_publisher_prefix(later_label, html), later_label)


if __name__ == "__main__":
    unittest.main()
