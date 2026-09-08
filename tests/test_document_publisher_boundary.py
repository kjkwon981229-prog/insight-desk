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


if __name__ == "__main__":
    unittest.main()
