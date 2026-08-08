#!/usr/bin/env python3

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from google import genai


# ============================================================
# DIRECTORIES
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# INPUT REPORTS
# ============================================================

TRIVY_REPORT = INPUT_DIR / "trivy-image-report.json"
ZAP_REPORT = INPUT_DIR / "zap-report.xml"
SBOM_REPORT = INPUT_DIR / "dummy-upi-app-cyclonedx.json"
COSIGN_REPORT = INPUT_DIR / "cosign-verification.txt"


# ============================================================
# OUTPUT REPORTS
# ============================================================

REMEDIATION_JSON = OUTPUT_DIR / "ai-remediation.json"
REMEDIATION_MD = OUTPUT_DIR / "ai-remediation.md"


# ============================================================
# GENERIC JSON LOADER
# ============================================================

def load_json_report(path):
    """
    Load and parse a JSON security report.
    """

    if not path.exists():
        raise FileNotFoundError(f"Report not found: {path}")

    try:
        return json.loads(path.read_text(encoding="utf-8"))

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in report: {path}"
        ) from exc


# ============================================================
# TRIVY
# ============================================================

def load_trivy_report():
    """
    Load Trivy JSON report.
    """

    return load_json_report(TRIVY_REPORT)


def extract_fixable_vulnerabilities(report):
    """
    Extract Trivy vulnerabilities that have a FixedVersion.
    """

    vulnerabilities = []

    for result in report.get("Results", []):

        for vuln in result.get("Vulnerabilities", []) or []:

            fixed_version = vuln.get("FixedVersion", "")

            if fixed_version:

                vulnerabilities.append(
                    {
                        "vulnerability_id": vuln.get(
                            "VulnerabilityID",
                            "UNKNOWN"
                        ),
                        "severity": vuln.get(
                            "Severity",
                            "UNKNOWN"
                        ),
                        "package": vuln.get(
                            "PkgName",
                            "UNKNOWN"
                        ),
                        "installed_version": vuln.get(
                            "InstalledVersion",
                            "UNKNOWN"
                        ),
                        "fixed_version": fixed_version,
                        "title": vuln.get(
                            "Title",
                            ""
                        ),
                        "target": result.get(
                            "Target",
                            "UNKNOWN"
                        ),
                    }
                )

    return vulnerabilities


# ============================================================
# ZAP
# ============================================================

def load_zap_report():
    """
    Load and parse OWASP ZAP XML report.
    """

    if not ZAP_REPORT.exists():
        raise FileNotFoundError(
            f"ZAP report not found: {ZAP_REPORT}"
        )

    try:
        root = ET.parse(ZAP_REPORT).getroot()

    except ET.ParseError as exc:
        raise ValueError(
            f"Invalid XML in ZAP report: {ZAP_REPORT}"
        ) from exc

    alerts = []

    for alert in root.findall(".//alertitem"):

        name = alert.findtext(
            "name",
            default="Unknown"
        )

        riskcode = alert.findtext(
            "riskcode",
            default="0"
        )

        confidence = alert.findtext(
            "confidence",
            default="0"
        )

        desc = alert.findtext(
            "desc",
            default=""
        ).strip()

        solution = alert.findtext(
            "solution",
            default=""
        ).strip()

        instances = alert.findall(
            ".//instances/instance"
        )

        instance_count = len(instances)

        alerts.append(
            {
                "name": name,
                "risk_code": riskcode,
                "confidence": confidence,
                "description": desc,
                "solution": solution,
                "instances": instance_count,
            }
        )

    return alerts


# ============================================================
# SBOM
# ============================================================

def load_sbom_report():
    """
    Load CycloneDX SBOM.

    SBOM is optional during local development because
    the local input directory may not contain it yet.
    """

    if not SBOM_REPORT.exists():

        print(
            "SBOM report not found locally. "
            "Continuing without SBOM evidence."
        )

        return None

    return load_json_report(SBOM_REPORT)


def summarize_sbom(report):
    """
    Extract useful information from CycloneDX SBOM.
    """

    if report is None:

        return {
            "available": False,
            "bom_format": "Unavailable",
            "spec_version": "Unavailable",
            "component_count": 0,
            "components": [],
        }

    components = report.get(
        "components",
        []
    )

    component_summary = []

    for component in components:

        component_summary.append(
            {
                "type": component.get(
                    "type",
                    "unknown"
                ),
                "name": component.get(
                    "name",
                    "unknown"
                ),
                "version": component.get(
                    "version",
                    "unknown"
                ),
                "purl": component.get(
                    "purl",
                    ""
                ),
            }
        )

    return {
        "available": True,
        "bom_format": report.get(
            "bomFormat",
            "Unknown"
        ),
        "spec_version": report.get(
            "specVersion",
            "Unknown"
        ),
        "component_count": len(
            components
        ),
        "components": component_summary,
    }


# ============================================================
# COSIGN
# ============================================================

def load_cosign_report():
    """
    Load Cosign verification output.

    Cosign evidence is optional during local development.
    """

    if not COSIGN_REPORT.exists():

        print(
            "Cosign verification report not found locally. "
            "Continuing without Cosign evidence."
        )

        return "Cosign verification evidence unavailable."

    return COSIGN_REPORT.read_text(
        encoding="utf-8"
    ).strip()


# ============================================================
# GEMINI
# ============================================================

def ask_gemini(
    vulnerabilities,
    zap_alerts,
    sbom_summary,
    cosign_status,
):
    """
    Send combined security evidence to Gemini
    and request remediation recommendations.
    """

    api_key = os.environ.get(
        "GEMINI_API_KEY"
    )

    if not api_key:

        raise RuntimeError(
            "GEMINI_API_KEY environment variable is not set."
        )

    client = genai.Client(
        api_key=api_key
    )

    prompt = f"""
You are a DevSecOps security remediation assistant.

Analyze the supplied security evidence from a Jenkins
DevSecOps security pipeline.

The evidence may contain:

1. Trivy container vulnerabilities
2. OWASP ZAP DAST findings
3. CycloneDX SBOM component information
4. Cosign image-signature verification output

Your task is to produce remediation recommendations.

IMPORTANT RULES:

- Do not claim that a vulnerability or finding is fixed.
- Do not invent package versions.
- Use only the supplied evidence.
- Trivy fixed versions may be used exactly as supplied.
- Do not invent fixed versions for ZAP findings.
- Do not treat SBOM components as vulnerabilities by themselves.
- If Cosign verification failed, recommend investigating image
  signing and artifact integrity.
- Clearly identify the source of every recommendation.
- Only mark a remediation as automatable when the supplied
  evidence supports a safe automated action.
- Do not assume that a package update is automatically safe.
- Mention compatibility or regression risk where appropriate.
- Return valid JSON only.
- Do not wrap the JSON in Markdown code fences.

Return this exact structure:

{{
  "remediations": [
    {{
      "source": "TRIVY|ZAP|SBOM|COSIGN",
      "vulnerability_id": "...",
      "severity": "...",
      "package": "...",
      "current_version": "...",
      "fixed_version": "...",
      "remediation": "...",
      "automatable": true,
      "risk": "LOW|MEDIUM|HIGH"
    }}
  ],
  "security_observations": [
    {{
      "source": "TRIVY|ZAP|SBOM|COSIGN",
      "finding": "...",
      "recommendation": "..."
    }}
  ]
}}

============================================================
TRIVY FIXABLE VULNERABILITIES
============================================================

{json.dumps(
    vulnerabilities,
    indent=2
)}

============================================================
OWASP ZAP FINDINGS
============================================================

{json.dumps(
    zap_alerts,
    indent=2
)}

============================================================
SBOM SUMMARY
============================================================

{json.dumps(
    sbom_summary,
    indent=2
)}

============================================================
COSIGN VERIFICATION OUTPUT
============================================================

{cosign_status}
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
    )

    return response.text


# ============================================================
# CLEAN GEMINI JSON
# ============================================================

def clean_json_response(response_text):
    """
    Convert Gemini response into valid JSON.
    """

    response_text = response_text.strip()

    # Remove Markdown code fences if Gemini
    # unexpectedly returns them.
    if response_text.startswith("```"):

        lines = response_text.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if (
            lines
            and lines[-1].strip() == "```"
        ):
            lines = lines[:-1]

        response_text = "\n".join(
            lines
        ).strip()

    try:

        return json.loads(
            response_text
        )

    except json.JSONDecodeError as exc:

        print(
            "Gemini returned invalid JSON."
        )

        print(
            "Raw Gemini response:"
        )

        print(response_text)

        raise ValueError(
            "Unable to parse Gemini response as JSON."
        ) from exc


# ============================================================
# MARKDOWN REPORT
# ============================================================

def generate_markdown(data):
    """
    Generate human-readable AI remediation report.
    """

    lines = [
        "# AI Remediation Report",
        "",
        (
            "Generated from Jenkins Trivy, OWASP ZAP, "
            "SBOM, and Cosign security evidence."
        ),
        "",
        "## Remediation Recommendations",
        "",
    ]

    remediations = data.get(
        "remediations",
        []
    )

    if not remediations:

        lines.append(
            "No remediation recommendations were generated."
        )

        lines.append("")

    for item in remediations:

        finding_id = item.get(
            "vulnerability_id",
            "Security Finding"
        )

        severity = item.get(
            "severity",
            "UNKNOWN"
        )

        source = item.get(
            "source",
            "UNKNOWN"
        )

        lines.append(
            f"### {finding_id} — {severity}"
        )

        lines.append("")

        lines.append(
            f"**Source:** `{source}`"
        )

        lines.append("")

        package = item.get(
            "package",
            ""
        )

        if package:

            lines.append(
                f"**Package:** `{package}`"
            )

            lines.append("")

        current_version = item.get(
            "current_version",
            ""
        )

        if current_version:

            lines.append(
                f"**Current Version:** "
                f"`{current_version}`"
            )

            lines.append("")

        fixed_version = item.get(
            "fixed_version",
            ""
        )

        if fixed_version:

            lines.append(
                f"**Fixed Version:** "
                f"`{fixed_version}`"
            )

            lines.append("")

        lines.append(
            "**Remediation:** "
            f"{item.get('remediation', 'Not provided')}"
        )

        lines.append("")

        lines.append(
            "**Automatable:** "
            f"`{item.get('automatable', False)}`"
        )

        lines.append("")

        lines.append(
            "**Risk:** "
            f"`{item.get('risk', 'UNKNOWN')}`"
        )

        lines.append("")

        lines.append("---")

        lines.append("")

    # ========================================================
    # SECURITY OBSERVATIONS
    # ========================================================

    lines.extend(
        [
            "## Security Observations",
            "",
        ]
    )

    observations = data.get(
        "security_observations",
        []
    )

    if not observations:

        lines.append(
            "No additional security observations were generated."
        )

        lines.append("")

    for observation in observations:

        source = observation.get(
            "source",
            "UNKNOWN"
        )

        finding = observation.get(
            "finding",
            ""
        )

        recommendation = observation.get(
            "recommendation",
            ""
        )

        lines.append(
            f"### {source}"
        )

        lines.append("")

        lines.append(
            f"**Finding:** {finding}"
        )

        lines.append("")

        lines.append(
            f"**Recommendation:** {recommendation}"
        )

        lines.append("")

        lines.append("---")

        lines.append("")

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print(
        "Loading Jenkins security evidence..."
    )

    # --------------------------------------------------------
    # TRIVY
    # --------------------------------------------------------

    trivy_report = load_trivy_report()

    vulnerabilities = extract_fixable_vulnerabilities(
        trivy_report
    )

    print(
        f"Found {len(vulnerabilities)} "
        "fixable Trivy vulnerabilities."
    )

    # --------------------------------------------------------
    # ZAP
    # --------------------------------------------------------

    zap_alerts = load_zap_report()

    print(
        f"Found {len(zap_alerts)} "
        "ZAP alert types."
    )

    # --------------------------------------------------------
    # SBOM
    # --------------------------------------------------------

    sbom_report = load_sbom_report()

    sbom_summary = summarize_sbom(
        sbom_report
    )

    if sbom_summary["available"]:

        print(
            "Loaded CycloneDX SBOM with "
            f"{sbom_summary['component_count']} "
            "components."
        )

    else:

        print(
            "CycloneDX SBOM evidence unavailable."
        )

    # --------------------------------------------------------
    # COSIGN
    # --------------------------------------------------------

    cosign_status = load_cosign_report()

    if COSIGN_REPORT.exists():

        print(
            "Loaded Cosign verification evidence."
        )

    else:

        print(
            "Cosign verification evidence unavailable."
        )

    # --------------------------------------------------------
    # GEMINI
    # --------------------------------------------------------

    print(
        "Sending combined security evidence "
        "to Gemini..."
    )

    response = ask_gemini(
        vulnerabilities,
        zap_alerts,
        sbom_summary,
        cosign_status,
    )

    # --------------------------------------------------------
    # PARSE RESPONSE
    # --------------------------------------------------------

    remediation_data = clean_json_response(
        response
    )

    # --------------------------------------------------------
    # WRITE JSON
    # --------------------------------------------------------

    REMEDIATION_JSON.write_text(
        json.dumps(
            remediation_data,
            indent=2
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # WRITE MARKDOWN
    # --------------------------------------------------------

    REMEDIATION_MD.write_text(
        generate_markdown(
            remediation_data
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # COMPLETE
    # --------------------------------------------------------

    print(
        "AI remediation analysis completed."
    )

    print(
        f"JSON: {REMEDIATION_JSON}"
    )

    print(
        f"Markdown: {REMEDIATION_MD}"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
