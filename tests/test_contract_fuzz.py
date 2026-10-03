"""Property-based tests over the contract parser's malformed-input surface.

The contract is the manufacturing-plan source of truth, so its validator
must fail closed on arbitrary input: every payload is either accepted as a
``ProdengContract`` or rejected with a ``ValidationError``/``ValueError`` —
an unexpected exception type escaping the parser is a bug.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from prodeng.contract import ProdengContract, load_contract

json_scalars = (
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text()
)
json_values = st.recursive(
    json_scalars,
    lambda children: st.lists(children) | st.dictionaries(st.text(), children),
    max_leaves=25,
)


@given(payload=json_values)
@settings(max_examples=200, deadline=None)
def test_model_validate_accepts_or_rejects_cleanly(payload: Any) -> None:
    try:
        ProdengContract.model_validate(payload)
    except ValidationError:
        return


@given(raw=st.text())
@settings(max_examples=100, deadline=None)
def test_load_contract_rejects_non_json_and_bad_contracts(raw: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "fuzz.prodeng.json"
        path.write_text(raw, encoding="utf-8")
        try:
            load_contract(path)
        except ValueError:
            return


@given(payload=st.dictionaries(st.text(), json_values))
@settings(max_examples=200, deadline=None)
def test_load_contract_json_documents(payload: dict[str, Any]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "fuzz.prodeng.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        try:
            load_contract(path)
        except ValueError:
            return


def test_example_contract_is_a_valid_baseline() -> None:
    contract = load_contract("examples/smart-kettle/smart-kettle.prodeng.json")
    assert isinstance(contract, ProdengContract)
