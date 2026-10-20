"""Golden tests for graph-based retrieval walk (Phase 1)."""

import pytest
import time
import tempfile
from pathlib import Path

from retrieval.graph import Graph, walk, Tier, explain, StaleIndexError
from retrieval.config import RetrievalConfig
from retrieval.seeds import seeds_from_bug_group


class TestGraphWalk:
    """Golden tests for graph walk implementation."""
    
    @pytest.fixture
    def data_processor_index(self, tmp_path):
        """Build index for data_processor fixture."""
        from indexer.index import RepoIndexer
        
        fixture_root = Path(__file__).parent.parent / "fixtures" / "data_processor"
        
        indexer = RepoIndexer(
            project_root=fixture_root,
            import_roots=["src"],
            test_dirs=["tests"],
            exclude_patterns=[],
            schema_version="1.2"
        )
        
        index_data = indexer.index()
        return index_data.to_dict(), fixture_root
    
    @pytest.fixture
    def calculator_index(self, tmp_path):
        """Build index for calculator fixture."""
        from indexer.index import RepoIndexer
        
        fixture_root = Path(__file__).parent.parent / "fixtures" / "sample_bugs"
        
        indexer = RepoIndexer(
            project_root=fixture_root,
            import_roots=["src"],
            test_dirs=["tests"],
            exclude_patterns=[],
            schema_version="1.2"
        )
        
        index_data = indexer.index()
        return index_data.to_dict(), fixture_root
    
    def test_g1_data_processor_filter_test(self, data_processor_index):
        """G1: data_processor seed test_filter_removes_invalid.
        
        Expected:
        - DataProcessor.filter: 0.90 FULL
        - _validate: 0.65 FULL
        - process: 0.41 SIGNATURE
        - sort: 0.29 SIGNATURE
        - aggregate: 0.18 DROP
        - DataProcessor class: 0.27 SKELETON
        
        Rank order: filter > _validate > process > sort > aggregate
        
        Note: If _validate uses MIN_VALUE/MAX_VALUE constants, they should score ~0.47 FULL.
        """
        index_dict, repo_root = data_processor_index
        graph = Graph(index_dict)
        
        # Seed: test_filter_removes_invalid
        test_sym_id = "tests/test_processor.py::test_filter_removes_invalid"
        seeds = {test_sym_id: 1.0}
        
        cfg = RetrievalConfig()
        hits = walk(graph, seeds, cfg)
        
        # Build lookup by symbol name
        hits_by_name = {}
        for hit in hits:
            name = hit.symbol_id.split('::')[-1]
            hits_by_name[name] = hit
        
        # Assertions with +-0.01 tolerance
        assert 'filter' in hits_by_name
        filter_hit = hits_by_name['filter']
        assert abs(filter_hit.score - 0.90) <= 0.01, f"filter score {filter_hit.score}"
        assert filter_hit.tier == Tier.FULL
        
        assert '_validate' in hits_by_name
        validate_hit = hits_by_name['_validate']
        assert abs(validate_hit.score - 0.65) <= 0.01, f"_validate score {validate_hit.score}"
        assert validate_hit.tier == Tier.FULL
        
        assert 'process' in hits_by_name
        process_hit = hits_by_name['process']
        assert abs(process_hit.score - 0.41) <= 0.01, f"process score {process_hit.score}"
        assert process_hit.tier == Tier.SIGNATURE
        
        assert 'sort' in hits_by_name
        sort_hit = hits_by_name['sort']
        assert abs(sort_hit.score - 0.29) <= 0.01, f"sort score {sort_hit.score}"
        assert sort_hit.tier == Tier.SIGNATURE
        
        # aggregate should be DROP or not present
        aggregate_score = hits_by_name.get('aggregate')
        if aggregate_score:
            assert abs(aggregate_score.score - 0.18) <= 0.01, f"aggregate score {aggregate_score.score}"
            assert aggregate_score.tier == Tier.DROP
        
        # DataProcessor class should be SKELETON
        assert 'DataProcessor' in hits_by_name
        class_hit = hits_by_name['DataProcessor']
        assert abs(class_hit.score - 0.27) <= 0.01, f"DataProcessor score {class_hit.score}"
        assert class_hit.tier == Tier.SKELETON
        
        # Check rank order (excluding DROP)
        included_hits = [h for h in hits if h.tier != Tier.DROP]
        included_names = [h.symbol_id.split('::')[-1] for h in included_hits]
        
        # Find positions
        filter_pos = included_names.index('filter')
        validate_pos = included_names.index('_validate')
        process_pos = included_names.index('process')
        sort_pos = included_names.index('sort')
        
        assert filter_pos < validate_pos < process_pos < sort_pos, \
            f"Rank order wrong: filter({filter_pos}) validate({validate_pos}) process({process_pos}) sort({sort_pos})"
        
        # Check for constants if _validate uses them
        # Need to inspect _validate source to check
        validate_sym_id = validate_hit.symbol_id
        validate_data = graph.symbols[validate_sym_id]
        if validate_data.get('references'):
            # Expect MIN_VALUE and MAX_VALUE
            for const_name in ['MIN_VALUE', 'MAX_VALUE']:
                if const_name in hits_by_name:
                    const_hit = hits_by_name[const_name]
                    assert abs(const_hit.score - 0.47) <= 0.05, f"{const_name} score {const_hit.score}"
                    assert const_hit.tier == Tier.FULL
    
    def test_g2_calculator_subtract(self, calculator_index):
        """G2: calculator seed test_subtract.
        
        Expected:
        - subtract: 0.90 FULL
        - Nothing else at SIGNATURE or above
        """
        index_dict, repo_root = calculator_index
        graph = Graph(index_dict)
        
        # Seed: test_subtract
        test_sym_id = "tests/test_calculator.py::test_subtract"
        seeds = {test_sym_id: 1.0}
        
        cfg = RetrievalConfig()
        hits = walk(graph, seeds, cfg)
        
        # Filter to non-DROP and non-test hits
        included_hits = [h for h in hits if h.tier != Tier.DROP and not h.symbol_id.startswith("tests/")]
        
        # Should only have subtract
        assert len(included_hits) == 1, f"Expected 1 hit, got {len(included_hits)}"
        
        subtract_hit = included_hits[0]
        assert 'subtract' in subtract_hit.symbol_id
        assert abs(subtract_hit.score - 0.90) <= 0.01, f"subtract score {subtract_hit.score}"
        assert subtract_hit.tier == Tier.FULL
    
    def test_g3_max_score_not_sum(self):
        """G3: A node reachable by two paths keeps max, not sum."""
        # Create synthetic graph
        symbols = {
            'test.py::test_a': {'kind': 'function', 'name': 'test_a', 'file': 'test.py',
                               'line_start': 1, 'line_end': 5, 'is_test': True, 'signature': '()'},
            'src.py::func_b': {'kind': 'function', 'name': 'func_b', 'file': 'src.py',
                              'line_start': 1, 'line_end': 5, 'is_test': False, 'signature': '()'},
            'src.py::func_c': {'kind': 'function', 'name': 'func_c', 'file': 'src.py',
                              'line_start': 10, 'line_end': 15, 'is_test': False, 'signature': '()'},
            'src.py::target': {'kind': 'function', 'name': 'target', 'file': 'src.py',
                              'line_start': 20, 'line_end': 25, 'is_test': False, 'signature': '()'},
        }
        
        # test_a calls both func_b and func_c, both call target
        # Path 1: test_a -tests-> func_b -calls-> target (score 1.0 * 1.0 * 0.9 * 0.8 * 0.9 = 0.648)
        # Path 2: test_a -tests-> func_c -calls-> target (score 1.0 * 1.0 * 0.9 * 0.8 * 0.9 = 0.648)
        # Max score for target should be 0.648, NOT 1.296
        
        call_graph = {
            'callees': {
                'test.py::test_a': ['src.py::func_b', 'src.py::func_c'],
                'src.py::func_b': ['src.py::target'],
                'src.py::func_c': ['src.py::target'],
            },
            'callers': {
                'src.py::func_b': ['test.py::test_a'],
                'src.py::func_c': ['test.py::test_a'],
                'src.py::target': ['src.py::func_b', 'src.py::func_c'],
            }
        }
        
        index_dict = {
            'symbols': symbols,
            'call_graph': call_graph,
            'files': {}
        }
        
        graph = Graph(index_dict)
        seeds = {'test.py::test_a': 1.0}
        
        cfg = RetrievalConfig()
        hits = walk(graph, seeds, cfg)
        
        target_hits = [h for h in hits if 'target' in h.symbol_id]
        assert len(target_hits) == 1
        
        target_hit = target_hits[0]
        # Score should be around 0.648 (max), not doubled
        expected = 1.0 * 1.0 * 0.9 * 0.8 * 0.9  # 0.648
        assert abs(target_hit.score - expected) <= 0.01, \
            f"Expected max score {expected}, got {target_hit.score}"
    
    def test_g4_hop_decay(self):
        """G4: A 3-hop chain scores strictly lower than 1-hop with same edge types."""
        symbols = {
            'test.py::test': {'kind': 'function', 'name': 'test', 'file': 'test.py',
                            'line_start': 1, 'line_end': 5, 'is_test': True, 'signature': '()'},
            'src.py::a': {'kind': 'function', 'name': 'a', 'file': 'src.py',
                         'line_start': 1, 'line_end': 5, 'is_test': False, 'signature': '()'},
            'src.py::b': {'kind': 'function', 'name': 'b', 'file': 'src.py',
                         'line_start': 10, 'line_end': 15, 'is_test': False, 'signature': '()'},
            'src.py::c': {'kind': 'function', 'name': 'c', 'file': 'src.py',
                         'line_start': 20, 'line_end': 25, 'is_test': False, 'signature': '()'},
            'src.py::direct': {'kind': 'function', 'name': 'direct', 'file': 'src.py',
                              'line_start': 30, 'line_end': 35, 'is_test': False, 'signature': '()'},
        }
        
        # Chain: test -tests-> a -calls-> b -calls-> c (3 hops)
        # Direct: test -tests-> direct (1 hop)
        call_graph = {
            'callees': {
                'test.py::test': ['src.py::a', 'src.py::direct'],
                'src.py::a': ['src.py::b'],
                'src.py::b': ['src.py::c'],
            },
            'callers': {
                'src.py::a': ['test.py::test'],
                'src.py::direct': ['test.py::test'],
                'src.py::b': ['src.py::a'],
                'src.py::c': ['src.py::b'],
            }
        }
        
        index_dict = {
            'symbols': symbols,
            'call_graph': call_graph,
            'files': {}
        }
        
        graph = Graph(index_dict)
        seeds = {'test.py::test': 1.0}
        
        cfg = RetrievalConfig()
        hits = walk(graph, seeds, cfg)
        
        c_hit = next(h for h in hits if 'src.py::c' in h.symbol_id)
        direct_hit = next(h for h in hits if 'src.py::direct' in h.symbol_id)
        
        # c is 3 hops, direct is 1 hop
        # c_score = 1.0 * 1.0 * 0.9 * 0.8 * 0.9 * 0.8 * 0.9 = 0.5184
        # direct_score = 1.0 * 1.0 * 0.9 = 0.9
        assert c_hit.score < direct_hit.score, \
            f"3-hop chain ({c_hit.score}) should score lower than 1-hop ({direct_hit.score})"
    
    def test_g5_hub_guard(self):
        """G5: A hub node with more than HUB_FAN_IN callers is not expanded through called_by."""
        # Create a hub function called by 10 non-test functions
        symbols = {
            'test.py::test': {'kind': 'function', 'name': 'test', 'file': 'test.py',
                            'line_start': 1, 'line_end': 5, 'is_test': True, 'signature': '()'},
            'src.py::target': {'kind': 'function', 'name': 'target', 'file': 'src.py',
                              'line_start': 1, 'line_end': 5, 'is_test': False, 'signature': '()'},
            'src.py::hub': {'kind': 'function', 'name': 'hub', 'file': 'src.py',
                           'line_start': 10, 'line_end': 15, 'is_test': False, 'signature': '()'},
        }
        
        # Add 10 caller functions
        call_graph = {
            'callees': {
                'test.py::test': ['src.py::target'],
                'src.py::target': ['src.py::hub'],
            },
            'callers': {
                'src.py::target': ['test.py::test'],
                'src.py::hub': ['src.py::target'],  # Will add more
            }
        }
        
        # Add 10 callers for hub
        for i in range(10):
            caller_id = f'src.py::caller{i}'
            symbols[caller_id] = {'kind': 'function', 'name': f'caller{i}', 'file': 'src.py',
                                 'line_start': 20+i, 'line_end': 25+i, 'is_test': False, 'signature': '()'}
            call_graph['callees'][caller_id] = ['src.py::hub']
            call_graph['callers']['src.py::hub'].append(caller_id)
        
        index_dict = {
            'symbols': symbols,
            'call_graph': call_graph,
            'files': {}
        }
        
        graph = Graph(index_dict)
        seeds = {'test.py::test': 1.0}
        
        cfg = RetrievalConfig()
        cfg.HUB_FAN_IN = 8  # Hub has 11 callers (10 + target), exceeds threshold
        hits = walk(graph, seeds, cfg)
        
        # Hub should be reached via target, but its callers should NOT be expanded
        caller_hits = [h for h in hits if 'caller' in h.symbol_id]
        assert len(caller_hits) == 0, f"Hub callers should not be expanded, found {len(caller_hits)}"
    
    def test_g6_stale_index(self, data_processor_index, tmp_path):
        """G6: A modified source file makes check_fresh raise StaleIndexError."""
        index_dict, repo_root = data_processor_index
        graph = Graph(index_dict)
        
        # Check fresh should pass initially
        graph.check_fresh(repo_root)
        
        # Modify a file
        processor_file = repo_root / "src" / "processor.py"
        original_content = processor_file.read_text()
        
        try:
            # Append a comment
            processor_file.write_text(original_content + "\n# Modified\n")
            
            # check_fresh should raise
            with pytest.raises(StaleIndexError) as exc_info:
                graph.check_fresh(repo_root)
            
            assert 'processor.py' in str(exc_info.value).lower()
        finally:
            # Restore
            processor_file.write_text(original_content)
    
    def test_g7_class_only_fallback(self):
        """G7: Test with only class target gives class 0.90 and methods 0.65 via contains."""
        symbols = {
            'test.py::test': {'kind': 'function', 'name': 'test', 'file': 'test.py',
                            'line_start': 1, 'line_end': 5, 'is_test': True, 'signature': '()'},
            'src.py::MyClass': {'kind': 'class', 'name': 'MyClass', 'file': 'src.py',
                               'line_start': 1, 'line_end': 20, 'is_test': False, 'signature': ''},
            'src.py::MyClass.method1': {'kind': 'method', 'name': 'method1', 'file': 'src.py',
                                       'line_start': 5, 'line_end': 10, 'is_test': False,
                                       'parent_class': 'MyClass', 'signature': '()'},
            'src.py::MyClass.method2': {'kind': 'method', 'name': 'method2', 'file': 'src.py',
                                       'line_start': 12, 'line_end': 18, 'is_test': False,
                                       'parent_class': 'MyClass', 'signature': '()'},
        }
        
        # Test only calls the class (instance-call resolution failed)
        call_graph = {
            'callees': {
                'test.py::test': ['src.py::MyClass'],
            },
            'callers': {
                'src.py::MyClass': ['test.py::test'],
            }
        }
        
        index_dict = {
            'symbols': symbols,
            'call_graph': call_graph,
            'files': {}
        }
        
        graph = Graph(index_dict)
        seeds = {'test.py::test': 1.0}
        
        cfg = RetrievalConfig()
        hits = walk(graph, seeds, cfg)
        
        # Check class score: 1.0 * 1.0 * 0.9 = 0.9
        class_hit = next(h for h in hits if h.symbol_id == 'src.py::MyClass')
        assert abs(class_hit.score - 0.90) <= 0.01, f"Class score {class_hit.score}"
        assert class_hit.tier == Tier.SKELETON
        
        # Check methods: 1.0 * 1.0 * 0.9 * 0.8 * 0.9 = 0.648 (tests edge, then contains)
        method_hits = [h for h in hits if 'method' in h.symbol_id]
        assert len(method_hits) == 2, f"Expected 2 methods, got {len(method_hits)}"
        
        for method_hit in method_hits:
            # Allow some tolerance around 0.65
            assert abs(method_hit.score - 0.65) <= 0.05, f"Method score {method_hit.score}"
            assert method_hit.tier in [Tier.FULL, Tier.SIGNATURE]
    
    def test_g8_test_nodes_not_hits(self):
        """G8: Test nodes never appear as hits unless they are seeds."""
        symbols = {
            'test.py::test_a': {'kind': 'function', 'name': 'test_a', 'file': 'test.py',
                               'line_start': 1, 'line_end': 5, 'is_test': True, 'signature': '()'},
            'test.py::test_b': {'kind': 'function', 'name': 'test_b', 'file': 'test.py',
                               'line_start': 10, 'line_end': 15, 'is_test': True, 'signature': '()'},
            'src.py::func': {'kind': 'function', 'name': 'func', 'file': 'src.py',
                            'line_start': 1, 'line_end': 5, 'is_test': False, 'signature': '()'},
        }
        
        # test_a calls func, test_b also calls func
        # func has test_b as caller, but test_b should never appear as a hit
        call_graph = {
            'callees': {
                'test.py::test_a': ['src.py::func'],
                'test.py::test_b': ['src.py::func'],
            },
            'callers': {
                'src.py::func': ['test.py::test_a', 'test.py::test_b'],
            }
        }
        
        index_dict = {
            'symbols': symbols,
            'call_graph': call_graph,
            'files': {}
        }
        
        graph = Graph(index_dict)
        seeds = {'test.py::test_a': 1.0}  # Only test_a is seed
        
        cfg = RetrievalConfig()
        hits = walk(graph, seeds, cfg)
        
        # test_b should NOT appear
        test_b_hits = [h for h in hits if 'test_b' in h.symbol_id]
        assert len(test_b_hits) == 0, "test_b should not appear as hit (not a seed)"
        
        # test_a should appear (it's a seed)
        test_a_hits = [h for h in hits if 'test_a' in h.symbol_id]
        assert len(test_a_hits) == 1, "test_a should appear (it's a seed)"
    
    def test_g9_deterministic(self, data_processor_index):
        """G9: Two runs give identical output."""
        index_dict, repo_root = data_processor_index
        graph = Graph(index_dict)
        
        seeds = {'tests/test_processor.py::test_filter_removes_invalid': 1.0}
        cfg = RetrievalConfig()
        
        # Run twice
        hits1 = walk(graph, seeds, cfg)
        hits2 = walk(graph, seeds, cfg)
        
        # Should be identical
        assert len(hits1) == len(hits2)
        
        for h1, h2 in zip(hits1, hits2):
            assert h1.symbol_id == h2.symbol_id
            assert abs(h1.score - h2.score) < 1e-10
            assert h1.hop == h2.hop
            assert h1.tier == h2.tier
            assert h1.path == h2.path
    
    def test_g10_performance(self):
        """G10: Synthetic 50k-symbol graph walks in under 0.5s."""
        # Create synthetic graph with 50k symbols
        symbols = {}
        call_graph = {'callees': {}, 'callers': {}}
        
        # Create seed
        symbols['test.py::test'] = {
            'kind': 'function', 'name': 'test', 'file': 'test.py',
            'line_start': 1, 'line_end': 5, 'is_test': True, 'signature': '()'
        }
        
        # Create a tree structure: seed calls 10 functions, each calls 10, etc.
        # 1 + 10 + 100 + 1000 + 10000 = 11111 nodes accessible
        # Plus 38889 unreachable nodes = 50000 total
        
        level = 0
        parent_ids = ['test.py::test']
        call_graph['callees']['test.py::test'] = []
        
        node_count = 1
        while node_count < 11111:
            new_parents = []
            for parent_id in parent_ids:
                for i in range(10):
                    if node_count >= 11111:
                        break
                    child_id = f'src.py::func{node_count}'
                    symbols[child_id] = {
                        'kind': 'function', 'name': f'func{node_count}', 'file': 'src.py',
                        'line_start': node_count, 'line_end': node_count+5,
                        'is_test': False, 'signature': '()'
                    }
                    if parent_id not in call_graph['callees']:
                        call_graph['callees'][parent_id] = []
                    call_graph['callees'][parent_id].append(child_id)
                    
                    if child_id not in call_graph['callers']:
                        call_graph['callers'][child_id] = []
                    call_graph['callers'][child_id].append(parent_id)
                    
                    new_parents.append(child_id)
                    node_count += 1
            
            parent_ids = new_parents
            level += 1
        
        # Add unreachable nodes
        while node_count < 50000:
            node_id = f'src.py::unreachable{node_count}'
            symbols[node_id] = {
                'kind': 'function', 'name': f'unreachable{node_count}', 'file': 'src.py',
                'line_start': node_count, 'line_end': node_count+5,
                'is_test': False, 'signature': '()'
            }
            node_count += 1
        
        index_dict = {
            'symbols': symbols,
            'call_graph': call_graph,
            'files': {}
        }
        
        graph = Graph(index_dict)
        seeds = {'test.py::test': 1.0}
        cfg = RetrievalConfig()
        
        start = time.time()
        hits = walk(graph, seeds, cfg)
        elapsed = time.time() - start
        
        assert elapsed < 0.5, f"Walk took {elapsed:.2f}s, expected < 0.5s"
        assert len(hits) > 0, "Should find some hits"
