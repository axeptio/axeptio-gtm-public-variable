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
import os
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

# The parameter that selects where a signal is read from. Only its own shape is
# checked; which sources exist is a template decision, not a gallery rule.
SOURCE_PARAM_NAME = "source"

# Cookie-name fields are TEXT parameters named like `jsonCookieName`. Their
# defaults must all appear in the get_cookies permission — getCookieValues on an
# undeclared name is refused at runtime, and the variable just returns undefined.
COOKIE_NAME_PARAM_SUFFIX = "CookieName"
GET_COOKIES_PERMISSION = "get_cookies"

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
    duplicated = []
    for index, marker in enumerate(markers):
        name = marker.group(1)
        end = markers[index + 1].start() if index + 1 < len(markers) else len(source)
        body = source[marker.end() : end].strip()
        # Keep the first occurrence and report the rest. Letting a later block win
        # would validate something Tag Manager may not use, and — worse — masks the
        # duplicate behind whatever error the wrong body happens to produce.
        if name in blocks:
            duplicated.append(name)
            continue
        blocks[name] = body

    for name in sorted(set(duplicated)):
        fail(
            "template-blocks",
            f"___{name}___ appears more than once; a template must declare each block once",
        )

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


def flatten_parameters(parameters: list) -> list:
    """Every parameter, including those nested in a GROUP's subParams.

    Tag Manager exposes a group's subParams on `data` exactly like a top-level field,
    so a check that only walked the outer list would miss them entirely.
    """
    flat = []
    for parameter in parameters:
        if not isinstance(parameter, dict):
            continue
        flat.append(parameter)
        subparams = parameter.get("subParams")
        if isinstance(subparams, list):
            flat.extend(flatten_parameters(subparams))
    return flat


def select_options(parameters: list, name: str, check: str) -> set | None:
    """The values a SELECT offers, or None if it is absent or malformed.

    Also enforces that its defaultValue is one of them: a default outside the list
    leaves the field blank on a fresh instance, so the template falls through to
    whatever its code treats as missing.
    """
    selector = next(
        (p for p in parameters if p.get("name") == name and p.get("type") == "SELECT"),
        None,
    )
    if selector is None:
        return None

    # Validate the shape before comparing. A non-mapping entry used to raise
    # AttributeError, and one missing `value` put None in the set, which produced a
    # nonsense "option [None] is missing" message and would raise TypeError in
    # sorted() as soon as a second one appeared.
    items = selector.get("selectItems")
    if not isinstance(items, list) or not items:
        fail(check, f"`{name}` SELECT has no selectItems")
        return None

    options = set()
    for position, item in enumerate(items):
        if not isinstance(item, dict) or not isinstance(item.get("value"), str):
            fail(
                check,
                f"`{name}` selectItems[{position}] is not an object with "
                f"a string `value`: {item!r}",
            )
            return None
        options.add(item["value"])

    default = selector.get("defaultValue")
    if default not in options:
        fail(
            check,
            f"`{name}` defaultValue {default!r} is not one of its "
            f"selectItems {sorted(options)}",
        )
    return options


def cookie_permission_names(permissions: list) -> set | None:
    """The cookies get_cookies is allowed to read, or None if it is not declared."""
    for entry in permissions:
        instance = (entry or {}).get("instance") or {}
        if (instance.get("key") or {}).get("publicId") != GET_COOKIES_PERMISSION:
            continue

        params = {
            p.get("key"): p.get("value") or {} for p in instance.get("param") or []
        }

        # As with read_data_layer, the name list only constrains anything when access
        # is "specific"; "any" hands the template every cookie on the domain.
        access = (params.get("cookieAccess") or {}).get("string")
        if access != "specific":
            fail(
                "template-permissions",
                f"get_cookies uses cookieAccess={access!r}; it must be 'specific' "
                "so the template only reads the cookies it declares",
            )
            return None

        return {
            item.get("string")
            for item in (params.get("cookieNames") or {}).get("listItem") or []
        }
    return None


def check_cookie_parity(parameters: list, permissions: list) -> None:
    """Every cookie-name field's default must be readable under get_cookies.

    Skipped when the template has no cookie-name fields. When it does, a default
    missing from the permission makes getCookieValues return nothing at runtime —
    the template silently loses its cookie fallback with no error to notice.
    """
    defaults = {
        p["defaultValue"]
        for p in parameters
        if p.get("type") == "TEXT"
        and isinstance(p.get("name"), str)
        and p["name"].endswith(COOKIE_NAME_PARAM_SUFFIX)
        and isinstance(p.get("defaultValue"), str)
        and p["defaultValue"]
    }
    if not defaults:
        return

    declared = cookie_permission_names(permissions)
    if declared is None:
        # None covers two cases: no permission at all, which nothing else reports, and
        # a permission that is present but malformed, which cookie_permission_names has
        # already failed on. Only diagnose the first, or one mistake reads as two.
        if not any(
            ((entry or {}).get("instance") or {}).get("key", {}).get("publicId")
            == GET_COOKIES_PERMISSION
            for entry in permissions
        ):
            fail(
                "template-cookies",
                f"the template has cookie-name field(s) {sorted(defaults)} but declares "
                f"no {GET_COOKIES_PERMISSION} permission, so it cannot read any cookie",
            )
        return

    unreadable = sorted(defaults - declared)
    if unreadable:
        fail(
            "template-cookies",
            f"cookie-name default(s) {unreadable} are missing from the "
            f"{GET_COOKIES_PERMISSION} cookieNames, so they would silently read nothing",
        )
    unreachable = sorted(declared - defaults)
    if unreachable:
        fail(
            "template-cookies",
            f"{GET_COOKIES_PERMISSION} grants {unreachable}, which no cookie-name "
            "field defaults to; drop the name or add the field",
        )


def check_signal_parity(parameters: list, permissions: list) -> None:
    """The signal selector and read_data_layer must offer exactly the same keys.

    Skipped when the template declares no `signal` selector — the parameter block was
    empty before the selector existed, and this is a consistency check, not a gallery
    rule. When it is present, an option missing from keyPatterns resolves to undefined
    at runtime with no error anywhere, which is the failure this exists to catch.
    """
    options = select_options(parameters, SIGNAL_PARAM_NAME, "template-signal")
    if options is None:
        return

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

    if parsed is None:
        fail(
            "template-tests", "___TESTS___ is empty; it must declare a `scenarios` list"
        )
        return
    if not isinstance(parsed, dict):
        fail(
            "template-tests",
            "___TESTS___ must be a mapping with a `scenarios` key, got "
            f"{type(parsed).__name__}",
        )
        return

    scenarios = parsed.get("scenarios")
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

    The temp file is closed before node opens it: Windows locks an open handle, so
    holding it would make the check fail for reasons that have nothing to do with the
    template.
    """
    handle, path = tempfile.mkstemp(suffix=".js")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as js:
            js.write("(function (data) {\n" + code + "\n});\n")
        result = subprocess.run(
            ["node", "--check", path], capture_output=True, text=True
        )
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

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

    # Any shape problem here is already reported by check_tests, so this only needs to
    # skip what it cannot read rather than diagnose it.
    try:
        import yaml

        parsed = yaml.safe_load(blocks.get("TESTS") or "")
    except Exception:  # noqa: BLE001 - a YAML parse error is reported by check_tests
        parsed = None

    scenarios = parsed.get("scenarios") if isinstance(parsed, dict) else None
    for scenario in scenarios if isinstance(scenarios, list) else []:
        if isinstance(scenario, dict) and isinstance(scenario.get("code"), str):
            fragments.append((f"scenario {scenario.get('name')!r}", scenario["code"]))

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
            # Group subParams reach `data` like any other field, so every check below
            # walks the flattened list rather than only the outer one.
            flat = flatten_parameters(parameters)
            check_signal_parity(flat, permissions)
            select_options(flat, SOURCE_PARAM_NAME, "template-source")
            check_cookie_parity(flat, permissions)
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
