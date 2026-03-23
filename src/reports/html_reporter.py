"""
HTML Report Generator for Cloud Cost Sentinel.
Generates an HTML report (CSS via <style> block) suitable for browser viewing
and S3 storage. Note: for full email-client compatibility, a CSS inliner such
as premailer would be needed, as some clients (e.g. Gmail) strip <style> tags.
"""

from datetime import datetime, timezone
from html import escape


_CSS = """
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
        background-color: #f5f5f5;
        margin: 0;
        padding: 20px;
        color: #333;
    }
    .container {
        max-width: 800px;
        margin: 0 auto;
        background-color: #ffffff;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.12);
    }
    .header {
        background-color: #1a1a2e;
        color: #ffffff;
        padding: 28px 32px;
    }
    .header h1 {
        margin: 0 0 6px 0;
        font-size: 22px;
        letter-spacing: 0.5px;
    }
    .header .meta {
        font-size: 13px;
        color: #a8b8d8;
        line-height: 1.7;
    }
    .section {
        padding: 24px 32px;
        border-bottom: 1px solid #eeeeee;
    }
    .section:last-child {
        border-bottom: none;
    }
    .section h2 {
        margin: 0 0 16px 0;
        font-size: 16px;
        color: #1a1a2e;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
    }
    th {
        background-color: #f0f4ff;
        color: #444;
        text-align: left;
        padding: 10px 12px;
        font-weight: 600;
        border-bottom: 2px solid #d0d8f0;
    }
    td {
        padding: 9px 12px;
        border-bottom: 1px solid #f0f0f0;
        vertical-align: top;
    }
    tr:last-child td {
        border-bottom: none;
    }
    tr:hover td {
        background-color: #fafbff;
    }
    .savings-row td {
        font-weight: 700;
        background-color: #fff8e1;
        color: #c17f00;
        border-top: 2px solid #ffe082;
    }
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-warn {
        background-color: #fff3cd;
        color: #856404;
    }
    .badge-ok {
        background-color: #d4edda;
        color: #155724;
    }
    .cost {
        color: #c0392b;
        font-weight: 600;
    }
    .zero-cost {
        color: #888;
    }
    .no-findings {
        color: #888;
        font-style: italic;
        font-size: 14px;
        padding: 8px 0;
    }
    .footer {
        background-color: #f8f9fa;
        padding: 16px 32px;
        font-size: 12px;
        color: #888;
        text-align: center;
    }
    @media (max-width: 600px) {
        body { padding: 8px; }
        .section, .header { padding: 16px; }
        table { font-size: 12px; }
        td, th { padding: 7px 8px; }
    }
"""


def _fmt_cost(value: float) -> str:
    if value == 0:
        return '<span class="zero-cost">$0.00</span>'
    return f'<span class="cost">${value:,.2f}</span>'


def _fmt_count(value: int) -> str:
    if value == 0:
        return '<span class="badge badge-ok">0</span>'
    return f'<span class="badge badge-warn">{value}</span>'


def _esc(value, default: str = "N/A") -> str:
    """HTML-escape a value for safe interpolation; substitutes default for None."""
    return escape(str(value if value is not None else default))


class HTMLReporter:
    """Generates an inline-CSS HTML cost report from all_findings."""

    def generate(self, all_findings: dict) -> str:
        """
        Build and return the full HTML report string.

        Args:
            all_findings: The dict produced by main.py after all scanners run.

        Returns:
            str: Complete HTML document.
        """
        account_id = all_findings.get("account_id", "N/A")
        region = all_findings.get("region", "N/A")
        scan_ts = all_findings.get("scan_timestamp", datetime.now(timezone.utc).isoformat())

        ec2 = all_findings.get("ec2", {})
        ebs = all_findings.get("ebs", {})
        rds = all_findings.get("rds", {})
        s3 = all_findings.get("s3", {})

        total_savings = (
            ec2.get("idle_instances_monthly_cost", 0)
            + ebs.get("unattached_volumes_monthly_cost", 0)
            + ebs.get("low_io_volumes_monthly_cost", 0)
            + rds.get("idle_instances_monthly_cost", 0)
            + rds.get("old_snapshots_monthly_cost", 0)
            + s3.get("unused_buckets_monthly_cost", 0)
        )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Cloud Cost Sentinel Report</title>
  <style>{_CSS}</style>
</head>
<body>
<div class="container">
  {self._header(account_id, region, scan_ts)}
  {self._summary_section(ec2, ebs, rds, s3, total_savings)}
  {self._ec2_section(ec2)}
  {self._ebs_section(ebs)}
  {self._rds_section(rds)}
  {self._s3_section(s3)}
  {self._footer(scan_ts)}
</div>
</body>
</html>"""
        return html

    # ------------------------------------------------------------------ #
    # Header
    # ------------------------------------------------------------------ #

    def _header(self, account_id: str, region: str, scan_ts: str) -> str:
        try:
            ts = datetime.fromisoformat(scan_ts.replace("Z", "+00:00"))
            readable = ts.strftime("%B %d, %Y at %H:%M UTC")
        except Exception:
            readable = scan_ts

        return f"""
  <div class="header">
    <h1>☁️ Cloud Cost Sentinel</h1>
    <div class="meta">
      <strong>Account ID:</strong> {_esc(account_id)}&nbsp;&nbsp;
      <strong>Region:</strong> {_esc(region)}<br>
      <strong>Scan Date:</strong> {readable}
    </div>
  </div>"""

    # ------------------------------------------------------------------ #
    # Summary table
    # ------------------------------------------------------------------ #

    def _summary_section(self, ec2: dict, ebs: dict, rds: dict, s3: dict, total: float) -> str:
        rows = [
            ("EC2", "Idle Instances",
             ec2.get("idle_instances_count", 0),
             ec2.get("idle_instances_monthly_cost", 0)),
            ("EBS", "Unattached Volumes",
             ebs.get("unattached_volumes_count", 0),
             ebs.get("unattached_volumes_monthly_cost", 0)),
            ("EBS", "Low I/O Volumes",
             ebs.get("low_io_volumes_count", 0),
             ebs.get("low_io_volumes_monthly_cost", 0)),
            ("RDS", "Idle Instances",
             rds.get("idle_instances_count", 0),
             rds.get("idle_instances_monthly_cost", 0)),
            ("RDS", "Old Snapshots",
             rds.get("old_snapshots_count", 0),
             rds.get("old_snapshots_monthly_cost", 0)),
            ("S3", "Unused Buckets",
             s3.get("unused_buckets_count", 0),
             s3.get("unused_buckets_monthly_cost", 0)),
        ]

        body_rows = ""
        for service, label, count, cost in rows:
            body_rows += f"""
        <tr>
          <td><strong>{service}</strong></td>
          <td>{label}</td>
          <td style="text-align:center">{_fmt_count(count)}</td>
          <td style="text-align:right">{_fmt_cost(cost)}/mo</td>
        </tr>"""

        return f"""
  <div class="section">
    <h2>Summary</h2>
    <table>
      <thead>
        <tr>
          <th>Service</th>
          <th>Finding</th>
          <th style="text-align:center">Count</th>
          <th style="text-align:right">Est. Monthly Cost</th>
        </tr>
      </thead>
      <tbody>
        {body_rows}
        <tr class="savings-row">
          <td colspan="2">💰 Total Potential Monthly Savings</td>
          <td></td>
          <td style="text-align:right">${total:,.2f}/mo</td>
        </tr>
      </tbody>
    </table>
  </div>"""

    # ------------------------------------------------------------------ #
    # EC2 detail
    # ------------------------------------------------------------------ #

    def _ec2_section(self, ec2: dict) -> str:
        instances = ec2.get("idle_instances", [])
        if not instances:
            return ""

        rows = ""
        for i in instances:
            rows += f"""
        <tr>
          <td><code>{_esc(i.get('instance_id'))}</code></td>
          <td>{_esc(i.get('instance_name'))}</td>
          <td>{_esc(i.get('instance_type'))}</td>
          <td style="text-align:right">{_esc(i.get('avg_cpu_percent'))}%</td>
          <td style="text-align:right">{_fmt_cost(i.get('estimated_monthly_cost', 0))}/mo</td>
        </tr>"""

        return f"""
  <div class="section">
    <h2>EC2 — Idle Instances</h2>
    <table>
      <thead>
        <tr>
          <th>Instance ID</th>
          <th>Name</th>
          <th>Type</th>
          <th style="text-align:right">Avg CPU</th>
          <th style="text-align:right">Est. Cost/mo</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>"""

    # ------------------------------------------------------------------ #
    # EBS detail
    # ------------------------------------------------------------------ #

    def _ebs_section(self, ebs: dict) -> str:
        unattached = ebs.get("unattached_volumes", [])
        low_io = ebs.get("low_io_volumes", [])

        if not unattached and not low_io:
            return ""

        sections = ""

        if unattached:
            rows = ""
            for v in unattached:
                rows += f"""
        <tr>
          <td><code>{_esc(v.get('VolumeId'))}</code></td>
          <td>{_esc(v.get('VolumeType'))}</td>
          <td style="text-align:right">{_esc(v.get('Size'))} GB</td>
          <td>{_esc(v.get('AvailabilityZone'))}</td>
          <td style="text-align:right">{_fmt_cost(v.get('estimated_monthly_cost', 0))}/mo</td>
        </tr>"""
            sections += f"""
    <p style="margin:0 0 8px;font-weight:600;font-size:14px;">Unattached Volumes</p>
    <table>
      <thead>
        <tr>
          <th>Volume ID</th>
          <th>Type</th>
          <th style="text-align:right">Size</th>
          <th>AZ</th>
          <th style="text-align:right">Est. Cost/mo</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""

        if low_io:
            rows = ""
            for v in low_io:
                rows += f"""
        <tr>
          <td><code>{_esc(v.get('VolumeId'))}</code></td>
          <td>{_esc(v.get('VolumeType'))}</td>
          <td style="text-align:right">{_esc(v.get('Size'))} GB</td>
          <td>{_esc(v.get('AvailabilityZone'))}</td>
          <td style="text-align:right">{_fmt_cost(v.get('estimated_monthly_cost', 0))}/mo</td>
        </tr>"""
            sections += f"""
    <p style="margin:16px 0 8px;font-weight:600;font-size:14px;">Low I/O Volumes</p>
    <table>
      <thead>
        <tr>
          <th>Volume ID</th>
          <th>Type</th>
          <th style="text-align:right">Size</th>
          <th>AZ</th>
          <th style="text-align:right">Est. Cost/mo</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""

        return f"""
  <div class="section">
    <h2>EBS — Volumes</h2>
    {sections}
  </div>"""

    # ------------------------------------------------------------------ #
    # RDS detail
    # ------------------------------------------------------------------ #

    def _rds_section(self, rds: dict) -> str:
        instances = rds.get("idle_instances", [])
        snapshots = rds.get("old_snapshots", [])

        if not instances and not snapshots:
            return ""

        sections = ""

        if instances:
            rows = ""
            for i in instances:
                rows += f"""
        <tr>
          <td><code>{_esc(i.get('db_instance_id'))}</code></td>
          <td>{_esc(i.get('db_instance_class'))}</td>
          <td>{_esc(i.get('engine'))} {_esc(i.get('engine_version', ''))}</td>
          <td style="text-align:right">{_esc(i.get('avg_cpu_percent'))}%</td>
          <td style="text-align:right">{_esc(i.get('avg_connections'))}</td>
          <td style="text-align:right">{_fmt_cost(i.get('estimated_monthly_cost', 0))}/mo</td>
        </tr>"""
            sections += f"""
    <p style="margin:0 0 8px;font-weight:600;font-size:14px;">Idle Instances</p>
    <table>
      <thead>
        <tr>
          <th>DB Instance ID</th>
          <th>Class</th>
          <th>Engine</th>
          <th style="text-align:right">Avg CPU</th>
          <th style="text-align:right">Avg Conns</th>
          <th style="text-align:right">Est. Cost/mo</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""

        if snapshots:
            rows = ""
            for s in snapshots:
                create_time = s.get("snapshot_create_time", "N/A")
                if hasattr(create_time, "strftime"):
                    create_time = create_time.strftime("%Y-%m-%d")
                elif isinstance(create_time, str) and "T" in create_time:
                    create_time = create_time.split("T")[0]
                rows += f"""
        <tr>
          <td><code>{_esc(s.get('snapshot_id'))}</code></td>
          <td>{_esc(s.get('db_instance_id'))}</td>
          <td>{_esc(s.get('engine'))}</td>
          <td style="text-align:right">{_esc(s.get('allocated_storage_gb'))} GB</td>
          <td>{_esc(create_time)}</td>
          <td style="text-align:right">{_fmt_cost(s.get('estimated_monthly_cost', 0))}/mo</td>
        </tr>"""
            sections += f"""
    <p style="margin:16px 0 8px;font-weight:600;font-size:14px;">Old Snapshots (&gt;90 days)</p>
    <table>
      <thead>
        <tr>
          <th>Snapshot ID</th>
          <th>DB Instance</th>
          <th>Engine</th>
          <th style="text-align:right">Size</th>
          <th>Created</th>
          <th style="text-align:right">Est. Cost/mo</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""

        return f"""
  <div class="section">
    <h2>RDS — Databases &amp; Snapshots</h2>
    {sections}
  </div>"""

    # ------------------------------------------------------------------ #
    # S3 detail
    # ------------------------------------------------------------------ #

    def _s3_section(self, s3: dict) -> str:
        buckets = s3.get("unused_buckets", [])
        if not buckets:
            return ""

        rows = ""
        for b in buckets:
            rows += f"""
        <tr>
          <td>{_esc(b.get('bucket_name'))}</td>
          <td>{_esc(b.get('region'))}</td>
          <td style="text-align:right">{_esc(b.get('size_formatted'))}</td>
          <td style="text-align:right">{_esc(b.get('object_count'))}</td>
          <td style="text-align:right">{_esc(b.get('total_requests', 0))}</td>
          <td style="text-align:right">{_fmt_cost(b.get('estimated_monthly_cost', 0))}/mo</td>
        </tr>"""

        return f"""
  <div class="section">
    <h2>S3 — Unused Buckets</h2>
    <table>
      <thead>
        <tr>
          <th>Bucket Name</th>
          <th>Region</th>
          <th style="text-align:right">Size</th>
          <th style="text-align:right">Objects</th>
          <th style="text-align:right">Requests (period)</th>
          <th style="text-align:right">Est. Cost/mo</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>"""

    # ------------------------------------------------------------------ #
    # Footer
    # ------------------------------------------------------------------ #

    def _footer(self, scan_ts: str) -> str:
        try:
            ts = datetime.fromisoformat(scan_ts.replace("Z", "+00:00"))
            readable = ts.strftime("%B %d, %Y at %H:%M UTC")
        except Exception:
            readable = escape(scan_ts)
        return f"""
  <div class="footer">
    Generated by Cloud Cost Sentinel &mdash; {readable}<br>
    Costs are estimates based on AWS public pricing and may not reflect reserved/spot pricing or data transfer fees.
  </div>"""
