"""Inboxr command-line interface."""

from __future__ import annotations

import json
import sys
import webbrowser
from pathlib import Path

import click

from inboxr.consistency import check as consistency_check
from inboxr.consistency import repair as consistency_repair
from inboxr.eval import Rubric, build_agent, run_eval
from inboxr.scenarios import SCENARIO_TEMPLATES, generate_scenario
from inboxr.ui import write_report
from inboxr.workspace import generate_workspace


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """Inboxr — synthetic workspace generator for AI agent training."""


@main.command()
@click.option("--seed", type=int, default=42, help="RNG seed (deterministic output).")
@click.option(
    "--difficulty",
    type=click.Choice(["easy", "medium", "hard", "crisis"]),
    default="medium",
)
@click.option("--personas", "persona_count", type=int, default=12)
@click.option("--no-whatsapp", is_flag=True, default=False)
@click.option("--out", type=click.Path(), default="./workspace", help="Output directory.")
def generate(seed: int, difficulty: str, persona_count: int, no_whatsapp: bool, out: str) -> None:
    """Generate a full synthetic workspace."""
    workspace = generate_workspace(
        seed=seed,
        difficulty=difficulty,
        persona_count=persona_count,
        include_whatsapp=not no_whatsapp,
    )
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write each system to its own file for easy inspection
    for key, payload in workspace.items():
        if key == "meta":
            continue
        path = out_dir / f"{key}.json"
        path.write_text(json.dumps(payload, indent=2))

    (out_dir / "meta.json").write_text(json.dumps(workspace["meta"], indent=2))

    click.echo(f"Workspace generated at: {out_dir.resolve()}")
    click.echo(f"  User: {workspace['meta']['user']} <{workspace['meta']['user_email']}>")
    click.echo(f"  Difficulty: {difficulty}")
    click.echo(f"  Emails: {workspace['gmail']['summary']['total_threads']}")
    click.echo(
        f"  Calendar events: {workspace['calendar']['summary']['total_events']} "
        f"({workspace['calendar']['summary']['conflict_count']} conflicts)"
    )
    click.echo(f"  Drive files: {workspace['drive']['summary']['total_files']}")
    click.echo(
        f"  Slack channels: {workspace['slack']['summary']['total_channels']} "
        f"(mentions: {workspace['slack']['summary']['total_mentions']})"
    )


@main.command()
@click.option(
    "--template",
    type=click.Choice(list(SCENARIO_TEMPLATES.keys())),
    required=True,
    help="Which scenario template to generate.",
)
@click.option("--seed", type=int, default=42)
@click.option("--out", type=click.Path(), default="./scenario.json")
def scenario(template: str, seed: int, out: str) -> None:
    """Generate a scenario (workspace + task + success criteria)."""
    sc = generate_scenario(template, seed=seed)
    Path(out).write_text(json.dumps(sc, indent=2))
    click.echo(f"Scenario '{template}' written to {out}")
    click.echo(f"  Task: {sc['task'][:120]}...")
    click.echo(f"  Skills tested: {', '.join(sc['skills_tested'])}")


@main.command(name="list-scenarios")
def list_scenarios() -> None:
    """List available scenario templates."""
    for name, cfg in SCENARIO_TEMPLATES.items():
        click.echo(f"  {name:20s} — {cfg['description']}")


@main.command()
@click.option(
    "--workspace",
    "workspace_path",
    type=click.Path(exists=True),
    required=True,
    help="Path to a workspace directory or scenario JSON file.",
)
@click.option(
    "--repair",
    "do_repair",
    is_flag=True,
    default=False,
    help="Apply mechanical repairs and write the result back.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit the full report as JSON instead of a summary.",
)
def check(workspace_path: str, do_repair: bool, as_json: bool) -> None:
    """Validate cross-system consistency of a generated workspace or scenario."""
    path = Path(workspace_path)
    workspace, writer = _load_workspace(path)

    if do_repair:
        _, report = consistency_repair(workspace)
        writer(workspace)
    else:
        report = consistency_check(workspace)

    if as_json:
        click.echo(json.dumps(report.to_dict(), indent=2))
    else:
        click.echo(report.summary())
        for v in report.violations:
            click.echo(f"  [{v.severity:7s}] {v.system:8s} {v.code}: {v.message}")
        if do_repair and report.repaired:
            click.echo("\nRepaired:")
            for v in report.repaired:
                click.echo(f"  [{v.system:8s}] {v.code}: {v.message}")

    if not report.is_consistent and not do_repair:
        sys.exit(1)


@main.command(name="eval")
@click.option(
    "--scenario",
    "scenario_arg",
    required=True,
    help="Either a scenario template name or a path to a scenario JSON file.",
)
@click.option(
    "--agent",
    "agent_spec",
    default="mock",
    help="'mock', 'openai:<model>', or 'anthropic:<model>'.",
)
@click.option(
    "--judge", default="heuristic", help="'heuristic', 'anthropic:<model>', or 'openai:<model>'."
)
@click.option("--seed", type=int, default=42, help="Seed if generating a scenario by template.")
@click.option("--max-steps", type=int, default=10)
@click.option("--out", type=click.Path(), default=None, help="Write full EvalResult JSON here.")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Print full EvalResult JSON instead of summary.",
)
@click.option(
    "--ui",
    "open_ui",
    is_flag=True,
    default=False,
    help="Open an HTML dashboard in your browser after eval.",
)
@click.option(
    "--ui-out",
    "ui_out",
    type=click.Path(),
    default=None,
    help="Write HTML dashboard here (default: <out>.html or eval_report.html).",
)
def eval_cmd(
    scenario_arg: str,
    agent_spec: str,
    judge: str,
    seed: int,
    max_steps: int,
    out: str | None,
    as_json: bool,
    open_ui: bool,
    ui_out: str | None,
) -> None:
    """Run an agent against a scenario and score it."""
    # Resolve scenario: template name or json file
    if scenario_arg in SCENARIO_TEMPLATES:
        scenario = generate_scenario(scenario_arg, seed=seed)
    else:
        p = Path(scenario_arg)
        if not p.is_file():
            raise click.ClickException(f"Not a known template and not a file: {scenario_arg}")
        scenario = json.loads(p.read_text())

    agent = build_agent(agent_spec)
    rubric = Rubric(judge=judge)
    result = run_eval(scenario, agent, rubric=rubric, max_steps=max_steps)

    result_dict = result.to_dict()
    result_dict["seed"] = scenario.get("seed", seed)
    result_dict["_workspace"] = scenario.get("workspace", {})

    if out:
        clean = {k: v for k, v in result_dict.items() if k != "_workspace"}
        Path(out).write_text(json.dumps(clean, indent=2))
        click.echo(f"Full result written to {out}")

    if as_json:
        clean = {k: v for k, v in result_dict.items() if k != "_workspace"}
        click.echo(json.dumps(clean, indent=2))
    else:
        click.echo(result.summary())

    if open_ui or ui_out:
        html_path = (
            Path(ui_out)
            if ui_out
            else (Path(out).with_suffix(".html") if out else Path("eval_report.html"))
        )
        write_report(result_dict, html_path)
        click.echo(f"Dashboard written to {html_path}")
        if open_ui:
            webbrowser.open(html_path.resolve().as_uri())

    # Non-zero exit if score < 100% — convenient for CI
    if result.score < 1.0:
        sys.exit(1)


def _load_workspace(path: Path):
    """Return (workspace_dict, write_back_fn) for either layout."""
    if path.is_file():
        data = json.loads(path.read_text())
        workspace = data["workspace"] if "workspace" in data and "task" in data else data

        def write_back(ws):
            if "workspace" in data and "task" in data:
                data["workspace"] = ws
                path.write_text(json.dumps(data, indent=2))
            else:
                path.write_text(json.dumps(ws, indent=2))

        return workspace, write_back

    if path.is_dir():
        workspace: dict = {}
        for child in path.glob("*.json"):
            workspace[child.stem] = json.loads(child.read_text())
        if "personas" not in workspace and "meta" in workspace:
            # nothing more to do — personas live at top level of meta-layout
            pass

        def write_back(ws):
            for key, payload in ws.items():
                (path / f"{key}.json").write_text(json.dumps(payload, indent=2))

        return workspace, write_back

    raise click.ClickException(f"Workspace path not recognized: {path}")


if __name__ == "__main__":
    main()
