import pytest

from llm_red.dataset import Attack, load_attacks


def test_real_catalog_loads_and_validates():
    attacks = load_attacks()
    assert attacks, "catalog should not be empty"
    assert all(isinstance(a, Attack) for a in attacks)
    # ids are unique across the whole catalog
    ids = [a.id for a in attacks]
    assert len(ids) == len(set(ids))
    # the seeded direct-injection family is present
    assert any(a.family == "direct_injection" for a in attacks)


def test_missing_required_field_raises(tmp_path):
    (tmp_path / "bad.yaml").write_text(
        "family: direct_injection\nattacks:\n  - id: x-1\n    payload: hi\n"
    )
    with pytest.raises(ValueError, match="missing"):
        load_attacks(tmp_path)


def test_family_mismatch_raises(tmp_path):
    (tmp_path / "f.yaml").write_text(
        "family: direct_injection\n"
        "attacks:\n"
        "  - id: x-1\n"
        "    family: jailbreak\n"
        "    payload: hi\n"
        "    bypass_when: leaks\n"
        "    safe_when: refuses\n"
    )
    with pytest.raises(ValueError, match="declares family"):
        load_attacks(tmp_path)


def test_duplicate_ids_raise(tmp_path):
    body = (
        "family: direct_injection\n"
        "attacks:\n"
        "  - id: dup\n"
        "    payload: a\n"
        "    bypass_when: x\n"
        "    safe_when: y\n"
        "  - id: dup\n"
        "    payload: b\n"
        "    bypass_when: x\n"
        "    safe_when: y\n"
    )
    (tmp_path / "d.yaml").write_text(body)
    with pytest.raises(ValueError, match="duplicate"):
        load_attacks(tmp_path)
