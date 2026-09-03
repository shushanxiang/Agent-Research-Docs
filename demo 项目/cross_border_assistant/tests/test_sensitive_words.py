# -*- coding: utf-8 -*-
"""utils/sensitive_words.py 测试：词表加载、敏感词过滤与高亮"""
from utils.sensitive_words import BUILTIN_WORDS, load_sensitive_words, filter_sensitive


def test_load_builtin_when_file_missing(tmp_path):
    words = load_sensitive_words(str(tmp_path / "not_exist.txt"))
    assert words == [w.lower() for w in BUILTIN_WORDS]


def test_load_from_file(tmp_path):
    f = tmp_path / "words.txt"
    f.write_text("best\n畅销\n\n销量第一\n", encoding="utf-8")
    words = load_sensitive_words(str(f))
    assert "best" in words
    assert "畅销" in words
    assert "销量第一" in words
    # 空行应被过滤
    assert all(w.strip() for w in words)


def test_filter_returns_hits_and_highlight(tmp_path):
    f = tmp_path / "w.txt"
    f.write_text("best\n销量第一\n", encoding="utf-8")
    words = load_sensitive_words(str(f))
    text = "This is the best product, 销量第一"
    highlighted, hits = filter_sensitive(text, words)
    assert "best" in hits
    assert "销量第一" in hits
    assert '<span style="color:red;font-weight:bold;">' in highlighted


def test_filter_no_hits():
    text = "normal product description"
    highlighted, hits = filter_sensitive(text, ["best"])
    assert hits == []
    assert highlighted == text


def test_filter_empty_text():
    highlighted, hits = filter_sensitive("", ["best"])
    assert highlighted == ""
    assert hits == []


def test_filter_case_insensitive_english():
    text = "BEST product"
    highlighted, hits = filter_sensitive(text, ["best"])
    assert hits == ["best"]
    assert "BEST" in highlighted  # 原文保留大小写，仅包裹高亮
