"""Prospective semantic identity; never rewrites or relabels stored events.

The versioned manifest declares signal symbols and research definitions. Source
verification is separate from identity: edits require an explicit manifest review.
Measurement versions are independent of signal identity and outcome maturation.
"""
import ast
import copy
import hashlib
import json
import math
import os
from pathlib import Path
from .schemas import digest, strict_loads

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = 'RESEARCH_SEMANTICS_V1'

class _WithoutDocs(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            node.body = node.body[1:]
        return node
    visit_ClassDef = visit_FunctionDef


def logic_digest(path, symbols):
    """Selected definitions plus their module-local helpers/constants, no I/O."""
    tree = ast.parse(Path(path).read_text())
    definitions = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            definitions[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name): definitions[target.id] = node
    selected = set()
    pending = list(symbols)
    while pending:
        name = pending.pop()
        if name in selected: continue
        if name not in definitions: raise ValueError('MISSING_SEMANTIC_SYMBOL:' + name)
        selected.add(name)
        pending.extend(n.id for n in ast.walk(definitions[name])
                       if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                       and n.id in definitions and n.id not in selected)
    payload = [ast.dump(_WithoutDocs().visit(copy.deepcopy(definitions[n])),
                        include_attributes=False) for n in sorted(selected)]
    return hashlib.sha256(json.dumps(payload, separators=(',', ':')).encode()).hexdigest()


def load_contract(root=ROOT):
    root = Path(root)
    contract = strict_loads((root/'config/reproducibility_contract_v1.json').read_text())
    if contract['contract_version'] != CONTRACT: raise ValueError('UNKNOWN_SEMANTIC_CONTRACT')
    for module, definition in contract['logic'].items():
        if logic_digest(root/'scripts'/f'{module}.py', definition['symbols']) != definition['ast_sha256']:
            raise ValueError('UNREVIEWED_SEMANTIC_SOURCE_CHANGE:' + module)
    for name, expected in contract['research_definitions'].items():
        if strict_loads((root/'config'/name).read_text()) != expected:
            raise ValueError('UNREVIEWED_RESEARCH_DEFINITION_CHANGE:' + name)
    return contract


def configuration_identity(cfg, contract, environment=None):
    env = os.environ if environment is None else environment
    rules = dict(contract['effective_rules'])
    for name, default in rules.items():
        value = env.get(name, default)
        rules[name] = float(value) if isinstance(default, float) else str(value)
        if isinstance(rules[name], float) and not math.isfinite(rules[name]):
            raise ValueError('INVALID_EFFECTIVE_RESEARCH_RULE:' + name)
    return digest({'contract_version': contract['contract_version'],
                   'observation_identity': contract['observation_identity'],
                   'signal_schema_version': contract['signal_schema_version'],
                   'logic': contract['logic'], 'research_definitions': contract['research_definitions'],
                   'effective_rules': rules, 'paper_config': cfg})


def measurement_identity(contract):
    return digest(contract['measurement'])
