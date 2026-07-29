#!/usr/bin/env python3
"""Validate this repository against the GTM Community Template Gallery contract.

The gallery publishes no submission-status feedback and re-checks repositories on a
2-3 day cycle, so a violation is invisible until it becomes an outage: SUP-1008 was
found by a customer ~24h after the LICENSE was replaced. This script is the only
place a violation can be caught before it ships.

Contract: https://developers.google.com/tag-platform/tag-manager/templates/gallery

Beyond the gallery contract this also checks template.tpl for *internal*
consistency — that its blocks parse, and that the signal selector and the
read_data_layer permission agree. Those are not gallery rules, but nothing else
catches them: Tag Manager's sandbox is proprietary and has no CLI, so the
___TESTS___ scenarios can only be executed from the Tests tab of the GTM UI. A
malformed block otherwise stays green here and fails on import.

Run locally from the repository root:

    python3 scripts/validate-gallery.py

Exits 0 when every check passes, 1 otherwise. All violations are reported, not just
the first, so one CI run tells you everything that is wrong.
"""

# Keeps annotations lazy so `dict | None` and `list[str]` are never evaluated at
# import time. Without this the script needs Python 3.10+ and dies with a
# TypeError before running a single check on anything older — a poor failure for
# a validator contributors run locally on whatever python3 they happen to have.
# With it, 3.7+ works.
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

METADATA_PATH = Path("metadata.yaml")
TEMPLATE_PATH = Path("template.tpl")
LICENSE_PATH = Path("LICENSE")

# A template.tpl is a sequence of ___BLOCK___ markers, each alone on its line,
# followed by that block's body. Google's exporter always emits them in this order.
BLOCK_MARKER_RE = re.compile(r"^___([A-Z_]+)___$", re.M)

# Blocks Tag Manager requires in a web template. ___NOTES___ is optional.
REQUIRED_BLOCKS = (
    "TERMS_OF_SERVICE",
    "INFO",
    "TEMPLATE_PARAMETERS",
    "SANDBOXED_JS_FOR_WEB_TEMPLATE",
    "WEB_PERMISSIONS",
    "TESTS",
)

# The parameter that selects which dataLayer key the variable returns. Its
# selectItems must stay in lockstep with the read_data_layer keyPatterns below —
# an option with no matching pattern is silently unreadable at runtime.
SIGNAL_PARAM_NAME = "signal"
READ_DATA_LAYER_PERMISSION = "read_data_layer"

# The complete set of category values the gallery accepts.
ALLOWED_CATEGORIES = {
    "ADVERTISING",
    "AFFILIATE_MARKETING",
    "ANALYTICS",
    "ATTRIBUTION",
    "CHAT",
    "CONVERSIONS",
    "DATA_WAREHOUSING",
    "EMAIL_MARKETING",
    "EXPERIMENTATION",
    "HEAT_MAP",
    "LEAD_GENERATION",
    "MARKETING",
    "PERSONALIZATION",
    "REMARKETING",
    "SALES",
    "SESSION_RECORDING",
    "SOCIAL",
    "SURVEY",
    "TAG_MANAGEMENT",
    "UTILITY",
}

# Phrases that must never appear in LICENSE. Replacing the Apache 2.0 text with
# Axeptio's proprietary notice is what caused SUP-1008 — the gallery requires the
# contents to be *only* Apache 2.0.
FORBIDDEN_IN_LICENSE = (
    "axeptio_contract",
    "IMPORTANT LICENSE NOTICE",
    "AVIS IMPORTANT",
)

errors: list[str] = []
warnings: list[str] = []


def fail(check: str, detail: str) -> None:
    errors.append(f"{check}: {detail}")


def warn(check: str, detail: str) -> None:
    warnings.append(f"{check}: {detail}")


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(("git",) + args, capture_output=True, text=True)


def check_required_files() -> None:
    """Required files, at the repository root, with exact casing."""
    for path in (LICENSE_PATH, METADATA_PATH, TEMPLATE_PATH):
        if not path.is_file():
            fail("required-files", f"{path} is missing from the repository root")

    # The gallery requires the licence filename in all caps. A case-insensitive
    # filesystem (macOS) resolves LICENSE/license alike, so ask git, which is
    # case-sensitive and matches what GitHub actually serves.
    tracked = git("ls-files").stdout.split()
    if LICENSE_PATH.is_file() and "LICENSE" not in tracked:
        fail(
            "required-files", "LICENSE is not tracked at the root with all-caps casing"
        )

    # "Each Git repository should only have one template.tpl file."
    tpls = [p for p in tracked if p.endswith("template.tpl")]
    if len(tpls) > 1:
        fail(
            "single-template",
            f"expected exactly one template.tpl, found {len(tpls)}: {tpls}",
        )
    elif tpls and tpls != ["template.tpl"]:
        fail(
            "single-template",
            f"template.tpl must be at the repository root, found at {tpls[0]}",
        )


def check_license() -> None:
    if not LICENSE_PATH.is_file():
        return
    body = LICENSE_PATH.read_text(encoding="utf-8")

    if "Apache License" not in body or "Version 2.0" not in body:
        fail("license-apache", "LICENSE does not contain the Apache License 2.0 text")
    if "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION" not in body:
        fail(
            "license-apache",
            "LICENSE is missing the Apache 2.0 terms and conditions body",
        )

    for phrase in FORBIDDEN_IN_LICENSE:
        if phrase.lower() in body.lower():
            fail(
                "license-only-apache",
                f"LICENSE contains {phrase!r}. The gallery requires the contents to be "
                "ONLY Apache 2.0 and delists templates that differ (SUP-1008).",
            )


def load_metadata() -> dict | None:
    if not METADATA_PATH.is_file():
        return None
    try:
        import yaml
    except ImportError:
        fail("metadata-parse", "PyYAML is not installed (pip install pyyaml)")
        return None
    try:
        data = yaml.safe_load(METADATA_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - any parse error is a failure
        fail("metadata-parse", f"metadata.yaml is not valid YAML: {exc}")
        return None
    if not isinstance(data, dict):
        fail("metadata-parse", "metadata.yaml does not parse to a mapping")
        return None
    return data


def check_metadata_fields(data: dict) -> list:
    for field in ("homepage", "documentation"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            fail("metadata-fields", f"`{field}` is missing or empty")
        elif not value.startswith(("http://", "https://")):
            fail("metadata-fields", f"`{field}` is not a URL: {value!r}")

    versions = data.get("versions")
    if not isinstance(versions, list) or not versions:
        fail("metadata-fields", "`versions` is missing or empty")
        return []
    return versions


def check_versions(versions: list) -> None:
    """Every sha must be real and on the current branch, newest first."""
    shas = []
    for index, entry in enumerate(versions):
        if not isinstance(entry, dict) or "sha" not in entry:
            fail("versions-shape", f"versions[{index}] has no `sha`")
            continue
        # str() because YAML types an all-digit sha as an int. A real one is
        # effectively never all digits, and the coercion loses leading zeros so
        # the hex check below rejects it — noisy but fail-safe, never a silent pass.
        sha = str(entry["sha"])
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            fail(
                "versions-sha",
                f"versions[{index}].sha is not a 40-character hex commit: {sha!r}. "
                "A placeholder here would break the gallery.",
            )
            continue
        if git("cat-file", "-e", f"{sha}^{{commit}}").returncode != 0:
            fail(
                "versions-sha",
                f"versions[{index}].sha {sha[:8]} does not exist in this repository",
            )
            continue
        if git("merge-base", "--is-ancestor", sha, "HEAD").returncode != 0:
            fail(
                "versions-sha",
                f"versions[{index}].sha {sha[:8]} is not an ancestor of HEAD — "
                "the gallery serves template.tpl from that commit, so it must be on the branch",
            )
            continue
        shas.append((index, sha))

    # "ordered in reverse chronological order, (most recent to oldest)" — this is
    # what the gallery indexes by, so a mis-ordered list publishes the wrong version.
    for (i, newer), (j, older) in zip(shas, shas[1:]):
        if git("merge-base", "--is-ancestor", older, newer).returncode != 0:
            fail(
                "versions-order",
                f"versions[{i}] ({newer[:8]}) is not a descendant of versions[{j}] ({older[:8]}); "
                "entries must be newest first",
            )


def check_latest_marker() -> None:
    """The `# Latest version` marker is a comment, so YAML parsing cannot see it.

    It is part of Google's published sample and was removed once already, so check
    the raw text: the marker must sit directly above the first entry.
    """
    if not METADATA_PATH.is_file():
        return
    lines = METADATA_PATH.read_text(encoding="utf-8").splitlines()
    try:
        versions_at = next(
            i for i, l in enumerate(lines) if re.fullmatch(r"versions:\s*", l)
        )
    except StopIteration:
        fail("latest-marker", "no `versions:` key found in metadata.yaml")
        return

    after = [l for l in lines[versions_at + 1 :] if l.strip()]
    if not after:
        fail("latest-marker", "`versions:` has no entries")
        return
    if after[0].strip() != "# Latest version":
        fail(
            "latest-marker",
            f"the line after `versions:` should be `# Latest version`, found {after[0].strip()!r}",
        )


def load_template_blocks() -> dict | None:
    """Split template.tpl into {block name: body}, or None if it is unusable."""
    if not TEMPLATE_PATH.is_file():
        return None
    # UTF-8 with BOM — decoding as plain utf-8 corrupts the first marker.
    source = TEMPLATE_PATH.read_text(encoding="utf-8-sig")

    markers = list(BLOCK_MARKER_RE.finditer(source))
    if not markers:
        fail("template-blocks", "template.tpl contains no ___BLOCK___ markers")
        return None

    blocks = {}
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(source)
        blocks[marker.group(1)] = source[marker.end() : end].strip()

    for name in REQUIRED_BLOCKS:
        if name not in blocks:
            fail("template-blocks", f"template.tpl has no ___{name}___ block")
    return blocks


def parse_json_block(blocks: dict, name: str, check: str):
    """Parse one JSON block, reporting a parse error against `check`."""
    body = blocks.get(name)
    if body is None:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        fail(check, f"___{name}___ is not valid JSON: {exc}")
        return None


def check_template_info(blocks: dict) -> None:
    info = parse_json_block(blocks, "INFO", "template-info")
    if info is None:
        return

    categories = info.get("categories")
    if categories is None:
        fail(
            "template-categories",
            "___INFO___ has no `categories`. The gallery requires at least one "
            f"(max three) from: {', '.join(sorted(ALLOWED_CATEGORIES))}",
        )
        return
    if not isinstance(categories, list) or not 1 <= len(categories) <= 3:
        fail(
            "template-categories",
            f"`categories` must be a list of 1-3 values, got {categories!r}",
        )
        return
    unknown = [c for c in categories if c not in ALLOWED_CATEGORIES]
    if unknown:
        fail("template-categories", f"unsupported category value(s): {unknown}")


def read_data_layer_key_patterns(permissions: list) -> set | None:
    """The keys read_data_layer is allowed to read, or None if it is not declared."""
    for entry in permissions:
        instance = (entry or {}).get("instance") or {}
        if (instance.get("key") or {}).get("publicId") != READ_DATA_LAYER_PERMISSION:
            continue

        params = {
            p.get("key"): p.get("value") or {} for p in instance.get("param") or []
        }

        # keyPatterns only constrains anything when allowedKeys is "specific";
        # "any" makes the list decorative and hands the template the whole dataLayer.
        allowed = (params.get("allowedKeys") or {}).get("string")
        if allowed != "specific":
            fail(
                "template-permissions",
                f"read_data_layer uses allowedKeys={allowed!r}; it must be 'specific' "
                "so the template only reads the keys it declares",
            )
            return None

        return {
            item.get("string")
            for item in (params.get("keyPatterns") or {}).get("listItem") or []
        }
    return None


def check_signal_parity(parameters: list, permissions: list) -> None:
    """The signal selector and read_data_layer must offer exactly the same keys.

    Skipped when the template declares no `signal` selector — the parameter block was
    empty before the selector existed, and this is a consistency check, not a gallery
    rule. When it is present, an option missing from keyPatterns resolves to undefined
    at runtime with no error anywhere, which is the failure this exists to catch.
    """
    selector = next(
        (
            p
            for p in parameters
            if isinstance(p, dict)
            and p.get("name") == SIGNAL_PARAM_NAME
            and p.get("type") == "SELECT"
        ),
        None,
    )
    if selector is None:
        return

    options = {i.get("value") for i in selector.get("selectItems") or []}
    if not options:
        fail("template-signal", f"`{SIGNAL_PARAM_NAME}` SELECT has no selectItems")
        return

    default = selector.get("defaultValue")
    if default not in options:
        fail(
            "template-signal",
            f"`{SIGNAL_PARAM_NAME}` defaultValue {default!r} is not one of its "
            f"selectItems {sorted(options)}",
        )

    patterns = read_data_layer_key_patterns(permissions)
    if patterns is None:
        return

    unreadable = sorted(options - patterns)
    if unreadable:
        fail(
            "template-signal",
            f"selector option(s) {unreadable} are missing from the read_data_layer "
            "keyPatterns, so they would silently return undefined",
        )
    unreachable = sorted(patterns - options)
    if unreachable:
        fail(
            "template-signal",
            f"read_data_layer grants {unreachable}, which no selector option can "
            "reach; drop the pattern or add the option",
        )


def check_tests(blocks: dict) -> None:
    """The ___TESTS___ block must at least be well-formed and non-empty.

    Tag Manager's sandbox is proprietary and has no runner outside the GTM UI, so this
    cannot execute the scenarios — only prove they would load.
    """
    body = blocks.get("TESTS")
    if body is None:
        return
    try:
        import yaml
    except ImportError:
        return  # already reported by load_metadata

    try:
        parsed = yaml.safe_load(body)
    except Exception as exc:  # noqa: BLE001 - any parse error is a failure
        fail("template-tests", f"___TESTS___ is not valid YAML: {exc}")
        return

    scenarios = (parsed or {}).get("scenarios")
    if scenarios is None:
        fail("template-tests", "___TESTS___ has no `scenarios` key")
        return
    if not isinstance(scenarios, list):
        fail("template-tests", "___TESTS___ `scenarios` is not a list")
        return
    if not scenarios:
        warn(
            "template-tests",
            "___TESTS___ declares no scenarios; the template has no unit tests",
        )
        return

    seen = set()
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            fail("template-tests", f"scenarios[{index}] is not a mapping")
            continue
        name = scenario.get("name")
        if not isinstance(name, str) or not name.strip():
            fail("template-tests", f"scenarios[{index}] has no `name`")
        elif name in seen:
            fail("template-tests", f"duplicate scenario name {name!r}")
        else:
            seen.add(name)
        if not isinstance(scenario.get("code"), str) or not scenario["code"].strip():
            fail("template-tests", f"scenarios[{index}] has no `code`")


def node_syntax_error(code: str) -> str | None:
    """Syntax-check a fragment with `node --check`, or None if it parses.

    Wrapped in a function expression because the sandboxed JS block uses a top-level
    `return`, which is illegal in a script. Reported line numbers are therefore off
    by one. This checks syntax only — it does not emulate the sandbox, which rejects
    plenty of syntactically valid JavaScript.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as handle:
        handle.write("(function (data) {\n" + code + "\n});\n")
        handle.flush()
        result = subprocess.run(
            ["node", "--check", handle.name], capture_output=True, text=True
        )
    if result.returncode == 0:
        return None

    # node prints the offending source, then `SyntaxError: ...`, then a stack and a
    # version banner. Pick out the diagnosis; the banner is the last line and says
    # nothing. Fall back to the raw output rather than swallowing an unknown format.
    output = (result.stderr or result.stdout).strip()
    for line in output.splitlines():
        if re.match(r"^\w*Error: ", line.strip()):
            return line.strip()
    return " ".join(output.split())


def check_javascript_syntax(blocks: dict) -> None:
    if subprocess.run(["node", "--version"], capture_output=True).returncode != 0:
        warn("template-js", "node is not on PATH; skipped the JavaScript syntax check")
        return

    fragments = [
        (
            "___SANDBOXED_JS_FOR_WEB_TEMPLATE___",
            blocks.get("SANDBOXED_JS_FOR_WEB_TEMPLATE"),
        )
    ]

    try:
        import yaml

        scenarios = (yaml.safe_load(blocks.get("TESTS") or "") or {}).get("scenarios")
        for scenario in scenarios or []:
            if isinstance(scenario, dict) and isinstance(scenario.get("code"), str):
                fragments.append(
                    (f"scenario {scenario.get('name')!r}", scenario["code"])
                )
    except Exception:  # noqa: BLE001 - shape problems are already reported by check_tests
        pass

    for label, code in fragments:
        if not code:
            continue
        error = node_syntax_error(code)
        if error:
            fail("template-js", f"{label} does not parse: {error}")


def check_issues_enabled() -> None:
    """Documented but demonstrably not enforced, so this only warns.

    The sibling gallery repo axeptio/axeptio-gtm-public-variable has Issues disabled
    and remains listed, as did this repository for years.
    """
    result = subprocess.run(
        ["gh", "api", "repos/{owner}/{repo}", "--jq", ".has_issues"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return  # no gh or no token: not worth failing the build over
    if result.stdout.strip() == "false":
        warn(
            "issues-enabled",
            "GitHub Issues are disabled; the gallery docs ask for them to be on",
        )


def main() -> int:
    check_required_files()
    check_license()
    data = load_metadata()
    if data is not None:
        check_versions(check_metadata_fields(data))
        check_latest_marker()

    blocks = load_template_blocks()
    if blocks is not None:
        check_template_info(blocks)
        parameters = parse_json_block(blocks, "TEMPLATE_PARAMETERS", "template-params")
        permissions = parse_json_block(
            blocks, "WEB_PERMISSIONS", "template-permissions"
        )
        if isinstance(parameters, list) and isinstance(permissions, list):
            check_signal_parity(parameters, permissions)
        check_tests(blocks)
        check_javascript_syntax(blocks)

    check_issues_enabled()

    for warning in warnings:
        print(f"warning  {warning}")
    if errors:
        print(f"\n{len(errors)} gallery contract violation(s):\n", file=sys.stderr)
        for error in errors:
            print(f"  FAIL  {error}", file=sys.stderr)
        print(
            "\nSee https://developers.google.com/tag-platform/tag-manager/templates/gallery",
            file=sys.stderr,
        )
        return 1

    print("OK  repository satisfies the GTM Community Template Gallery contract")
    return 0


if __name__ == "__main__":
    sys.exit(main())
