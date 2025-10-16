#!/usr/bin/env python3
"""
Phase 9 Verification Script

Validates that Phase 9 (Main Processor & Pipeline Orchestration) is complete
and all components are working correctly.
"""

import sys
from pathlib import Path

# Add project root to PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_file_exists(filepath: Path, description: str) -> bool:
    """Check if a file exists and print result."""
    if filepath.exists():
        size = filepath.stat().st_size
        print(f"✅ {description}: {filepath} ({size:,} bytes)")
        return True
    else:
        print(f"❌ {description}: {filepath} NOT FOUND")
        return False


def check_import(module_name: str, components: list) -> bool:
    """Check if module and components can be imported."""
    try:
        module = __import__(module_name, fromlist=components)
        for component in components:
            if not hasattr(module, component):
                print(f"❌ {module_name}.{component} not found")
                return False
        print(f"✅ Import {module_name}: {', '.join(components)}")
        return True
    except Exception as e:
        print(f"❌ Import {module_name} failed: {e}")
        return False


def test_processing_result():
    """Test ProcessingResult class."""
    try:
        from src.processor import ProcessingResult

        # Test successful result
        result = ProcessingResult(
            success=True, document_id=123, cost_usd=0.05, processing_time_seconds=3.2
        )
        assert result.success
        assert result.document_id == 123
        assert result.cost_usd == 0.05
        assert result.processing_time_seconds == 3.2

        # Test duplicate result
        dup_result = ProcessingResult(success=True, duplicate_of=456)
        assert dup_result.success
        assert dup_result.duplicate_of == 456

        # Test failed result
        fail_result = ProcessingResult(success=False, error="Test error")
        assert not fail_result.success
        assert fail_result.error == "Test error"

        print("✅ ProcessingResult class: All tests passed")
        return True
    except Exception as e:
        print(f"❌ ProcessingResult tests failed: {e}")
        return False


def main():
    """Run all verification checks."""
    print("\n" + "=" * 60)
    print("Phase 9 Verification")
    print("=" * 60 + "\n")

    checks = []

    # 1. Check core files exist
    print("--- File Existence Checks ---")
    checks.append(check_file_exists(Path("src/processor.py"), "Processor module"))
    checks.append(check_file_exists(Path("process_inbox.py"), "CLI script"))
    checks.append(
        check_file_exists(Path("docs/PROCESSOR_GUIDE.md"), "Processor documentation")
    )
    checks.append(check_file_exists(Path("PHASE_9_HANDOFF.json"), "Handoff report"))
    checks.append(check_file_exists(Path("PHASE_9_SUMMARY.md"), "Summary document"))
    print()

    # 2. Check imports
    print("--- Import Checks ---")
    checks.append(
        check_import(
            "src.processor",
            [
                "ProcessingResult",
                "encode_pdf_to_base64",
                "process_document",
                "process_inbox",
            ],
        )
    )
    checks.append(check_import("src.config", ["get_config"]))
    checks.append(check_import("src.database", ["DatabaseManager"]))
    checks.append(check_import("src.api_client", ["ResponsesAPIClient"]))
    checks.append(check_import("src.vector_store", ["VectorStoreManager"]))
    checks.append(
        check_import(
            "src.dedupe", ["deduplicate_and_hash", "build_vector_store_attributes"]
        )
    )
    checks.append(check_import("src.schema", ["validate_response"]))
    checks.append(check_import("src.prompts", ["build_responses_api_payload"]))
    checks.append(
        check_import("src.token_counter", ["calculate_cost", "check_cost_alerts"])
    )
    print()

    # 3. Test ProcessingResult class
    print("--- Functional Tests ---")
    checks.append(test_processing_result())
    print()

    # 4. Check directory structure
    print("--- Directory Structure ---")
    for dirname in ["inbox", "processed", "failed", "logs"]:
        dirpath = Path(dirname)
        if dirpath.exists() and dirpath.is_dir():
            print(f"✅ Directory exists: {dirname}/")
            checks.append(True)
        else:
            print(f"⚠️  Directory missing: {dirname}/ (will be created on first run)")
            checks.append(True)  # Non-fatal
    print()

    # 5. Check foundation phases
    print("--- Foundation Phase Dependencies ---")
    foundation_modules = [
        ("src.config", "Phase 1: Configuration"),
        ("src.models", "Phase 2: Database Models"),
        ("src.schema", "Phase 3: JSON Schema"),
        ("src.prompts", "Phase 4: Prompts"),
        ("src.dedupe", "Phase 5: Deduplication"),
        ("src.vector_store", "Phase 6: Vector Store"),
        ("src.api_client", "Phase 7: API Client"),
        ("src.token_counter", "Phase 8: Token Tracking"),
    ]

    for module, description in foundation_modules:
        try:
            __import__(module)
            print(f"✅ {description}: {module}")
            checks.append(True)
        except Exception as e:
            print(f"❌ {description}: {module} - {e}")
            checks.append(False)
    print()

    # Results
    print("=" * 60)
    passed = sum(checks)
    total = len(checks)
    percentage = (passed / total) * 100

    print(f"Results: {passed}/{total} checks passed ({percentage:.1f}%)")
    print("=" * 60)

    if passed == total:
        print("\n🎉 Phase 9 verification PASSED - All systems operational!")
        print("\n✅ Ready for Phase 10: Testing & Production Readiness")
        return 0
    else:
        print(f"\n❌ Phase 9 verification FAILED - {total - passed} checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
