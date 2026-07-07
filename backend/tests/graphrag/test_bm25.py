from regulaforge.graphrag.infrastructure.bm25_index import BM25Index


class TestBM25Index:
    def test_empty_index(self):
        bm25 = BM25Index()
        results = bm25.search("test query")
        assert results == []

    def test_single_document(self):
        bm25 = BM25Index()
        bm25.add_document("doc1", "The Reserve Bank of India regulates banking")
        bm25.build()
        results = bm25.search("Reserve Bank")
        assert len(results) >= 1
        assert results[0]["id"] == "doc1"
        assert results[0]["score"] > 0

    def test_multiple_documents(self):
        bm25 = BM25Index()
        docs = [
            {"id": "doc1", "text": "RBI regulates banking sector in India"},
            {"id": "doc2", "text": "SEBI regulates stock markets and investors"},
            {"id": "doc3", "text": "IRDAI regulates insurance companies"},
        ]
        bm25.add_documents(docs)
        bm25.build()

        rbi_results = bm25.search("RBI banking")
        assert rbi_results[0]["id"] == "doc1"

        sebi_results = bm25.search("SEBI stock market")
        assert sebi_results[0]["id"] == "doc2"

    def test_relevance_ranking(self):
        bm25 = BM25Index()
        docs = [
            {"id": "doc1", "text": "compliance requirements for banking sector regulatory framework"},
            {"id": "doc2", "text": "banking compliance and regulatory requirements for all banks"},
            {"id": "doc3", "text": "weather forecast sunny skies clear conditions"},
        ]
        bm25.add_documents(docs)
        bm25.build()

        results = bm25.search("banking compliance regulatory requirements")
        assert results[0]["id"] in ("doc1", "doc2")
        assert results[-1]["id"] == "doc3"

    def test_query_with_no_results(self):
        bm25 = BM25Index()
        bm25.add_document("doc1", "RBI regulations")
        bm25.build()
        results = bm25.search("xyznonexistentterm12345")
        assert all(r["score"] == 0.0 for r in results) or not results

    def test_tokenize_edge_cases(self):
        bm25 = BM25Index()
        bm25.add_document("doc1", "  Short  text  ")
        bm25.build()
        results = bm25.search("short")
        assert len(results) == 1

    def test_clear(self):
        bm25 = BM25Index()
        bm25.add_document("doc1", "Some text")
        bm25.build()
        assert len(bm25._documents) == 1
        bm25.clear()
        assert len(bm25._documents) == 0
        assert bm25._built is False

    def test_large_document(self):
        bm25 = BM25Index()
        large_text = "regulation " * 1000 + "compliance " * 500
        bm25.add_document("doc1", large_text)
        bm25.build()
        results = bm25.search("regulation compliance")
        assert len(results) == 1
        assert results[0]["score"] > 0

    def test_add_document_with_metadata(self):
        bm25 = BM25Index()
        bm25.add_document("doc1", "RBI circular", metadata={"year": 2024})
        bm25.build()
        results = bm25.search("RBI")
        assert results[0]["metadata"]["year"] == 2024
