"""
集成验证脚本：测试替换后的服务层完整链路
"""

import sys, json, time
sys.path.insert(0, '.')

# ====== 模拟数据 ======
MOCK = {
    'metadata': {
        'standard_code': 'GB 55037-2022',
        'title': '建筑防火通用规范',
        'status': '有效',
    },
    'chapters': [
        {
            'title': '安全疏散与避难设施',
            'clauses': [
                {
                    'clause_id': '4.1.3',
                    'content': '疏散走道的净宽度：单面布房不应小于1.30m，双面布房不应小于1.40m。人员密集的公共场所疏散门不应设置门槛，其宽度不应小于1.40m。',
                    'page_num': 45,
                },
                {
                    'clause_id': '4.1.1',
                    'content': '建筑内的安全出口和疏散门应分散布置，且每个防火分区相邻两个安全出口最近边缘之间的水平距离不应小于5m。',
                    'page_num': 42,
                },
            ],
        },
        {
            'title': '建筑保温',
            'clauses': [
                {
                    'clause_id': '5.1.2',
                    'content': '建筑高度大于27m的住宅建筑和建筑高度大于24m的非单层公共建筑，其外墙外保温材料的燃烧性能应为A级。',
                    'page_num': 60,
                },
                {
                    'clause_id': '5.1.3',
                    'content': '除本规范另有规定外，建筑外墙外保温材料的燃烧性能等级不应低于B1级。',
                    'page_num': 61,
                },
            ],
        },
        {
            'title': '建筑分类和耐火等级',
            'clauses': [
                {
                    'clause_id': '2.1.1',
                    'content': '民用建筑根据其建筑高度和层数可分为单、多层民用建筑和高层民用建筑。',
                    'page_num': 8,
                },
                {
                    'clause_id': '2.1.2',
                    'content': '防火墙的耐火极限不应低于3.00h，承重墙不应低于2.00h。',
                    'page_num': 10,
                },
            ],
        },
    ],
}

errors = []

# ═══ 1. 文本切块 ═══
try:
    from app.utils.chunking import chunk_clauses
    chunks = chunk_clauses(MOCK)
    assert len(chunks) == 6, f"expected 6, got {len(chunks)}"
    print(f'[PASS] 1. Chunking: {len(chunks)} chunks')
except Exception as e:
    errors.append(f'chunking: {e}')
    print(f'[FAIL] 1. Chunking: {e}')

# ═══ 2. 检索 ═══
try:
    from app.services.search import SearchService
    svc = SearchService()
    svc.load_regulation_chunks(chunks)
    query = '商场疏散走道的宽度要求是多少？'
    result = svc.search_regulations(query, top_k=3)
    assert result['total'] > 0, "zero results"
    top = result['results'][0]
    assert '4.1.3' in top['clause_id'], f"expected 4.1.3, got {top['clause_id']}"
    print(f'[PASS] 2. Search: top-1 = clause {top["clause_id"]} (score={top["score"]})')
except Exception as e:
    errors.append(f'search: {e}')
    print(f'[FAIL] 2. Search: {e}')

# ═══ 3. 规范问答（降级模式）═══
try:
    from app.services.chat import RegulationQAService
    qa = RegulationQAService(svc._regulation_retriever)
    answer = qa.answer(query, top_k=3)
    assert answer['answer'], "empty answer"
    assert len(answer['sources']) == 3, f"expected 3 sources, got {len(answer['sources'])}"
    assert answer['disclaimer'], "missing disclaimer"
    print(f'[PASS] 3. QA: {len(answer["sources"])} sources, disclaimer OK')
except Exception as e:
    errors.append(f'chat: {e}')
    print(f'[FAIL] 3. QA: {e}')

# ═══ 4. 元数据提取（规则引擎）═══
try:
    from app.services.parse import ParseService
    ps = ParseService()
    meta = ps.extract_metadata(
        'GB 55037-2022 建筑防火通用规范 2022年12月1日发布 2023年6月1日施行 中华人民共和国住房和城乡建设部'
    )
    assert meta['standard_code'] == 'GB 55037-2022', f"code mismatch: {meta['standard_code']}"
    assert meta['publisher'] != '', "empty publisher"
    assert meta['keywords'], "empty keywords"
    print(f'[PASS] 4. Metadata: code={meta["standard_code"]}, keywords={meta["keywords"]}')
except Exception as e:
    errors.append(f'parse: {e}')
    print(f'[FAIL] 4. Metadata: {e}')

# ═══ 5. LLM 可用性 ═══
try:
    from app.utils.llm import is_llm_available
    available = is_llm_available()
    status = 'dashscope OK' if available else 'dashscope not installed (fallback mode)'
    print(f'[INFO] 5. LLM: {status}')
except Exception as e:
    errors.append(f'llm: {e}')
    print(f'[FAIL] 5. LLM: {e}')

# ═══ 汇总 ═══
print()
if errors:
    print(f'FAILED: {len(errors)} error(s)')
    for e in errors:
        print(f'  - {e}')
    sys.exit(1)
else:
    print('All integration tests passed.')
