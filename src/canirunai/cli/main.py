from __future__ import annotations

import click

from ..sdk import CanIRunAI
from ..ui.terminal_printer import render_catalog_list, render_score_report, render_spec


def _sdk(config: str | None) -> CanIRunAI:
    return CanIRunAI(config_path=config)


@click.group()
@click.option("--config", type=click.Path(exists=True, dir_okay=False, path_type=str), default=None)
@click.pass_context
def cli(ctx: click.Context, config: str | None) -> None:
    ctx.ensure_object(dict)
    ctx.obj["sdk"] = _sdk(config)


@cli.group()
def update() -> None:
    pass


@update.command("cpu")
@click.option("--verbose", is_flag=True, default=False)
@click.pass_context
def update_cpu(ctx: click.Context, verbose: bool) -> None:
    catalog = ctx.obj["sdk"].update_cpu(verbose=verbose)
    click.echo(f"updated cpu catalog with {len(catalog.items)} items")


@update.command("gpu")
@click.option("--verbose", is_flag=True, default=False)
@click.pass_context
def update_gpu(ctx: click.Context, verbose: bool) -> None:
    catalog = ctx.obj["sdk"].update_gpu(verbose=verbose)
    click.echo(f"updated gpu catalog with {len(catalog.items)} items")


@update.command("model")
@click.option("--hfname", type=str, default=None)
@click.option("--verbose", is_flag=True, default=False)
@click.pass_context
def update_model(ctx: click.Context, hfname: str | None, verbose: bool) -> None:
    catalog = ctx.obj["sdk"].update_model(hfname, verbose=verbose)
    click.echo(f"updated model catalog with {len(catalog.items)} items")


@cli.group("list")
def list_group() -> None:
    pass


@list_group.command("cpu")
@click.option("--output", type=click.Choice(["wide", "json"]), default=None)
@click.pass_context
def list_cpu(ctx: click.Context, output: str | None) -> None:
    items = ctx.obj["sdk"].list_specs("cpu")
    click.echo(render_catalog_list(items, output=output or "default"))


@list_group.command("gpu")
@click.option("--output", type=click.Choice(["wide", "json"]), default=None)
@click.pass_context
def list_gpu(ctx: click.Context, output: str | None) -> None:
    items = ctx.obj["sdk"].list_specs("gpu")
    click.echo(render_catalog_list(items, output=output or "default"))


@list_group.command("model")
@click.option("--output", type=click.Choice(["wide", "json"]), default=None)
@click.pass_context
def list_model(ctx: click.Context, output: str | None) -> None:
    items = ctx.obj["sdk"].list_specs("model")
    click.echo(render_catalog_list(items, output=output or "default"))


@cli.group()
def get() -> None:
    pass


@get.command("cpu")
@click.argument("name")
@click.option("--output", type=click.Choice(["json"]), default=None)
@click.pass_context
def get_cpu(ctx: click.Context, name: str, output: str | None) -> None:
    click.echo(render_spec(ctx.obj["sdk"].get_spec("cpu", name), output=output or "default"))


@get.command("gpu")
@click.argument("name")
@click.option("--output", type=click.Choice(["json"]), default=None)
@click.pass_context
def get_gpu(ctx: click.Context, name: str, output: str | None) -> None:
    click.echo(render_spec(ctx.obj["sdk"].get_spec("gpu", name), output=output or "default"))


@get.command("model")
@click.argument("name")
@click.option("--output", type=click.Choice(["json"]), default=None)
@click.pass_context
def get_model(ctx: click.Context, name: str, output: str | None) -> None:
    click.echo(render_spec(ctx.obj["sdk"].get_spec("model", name), output=output or "default"))


@cli.command()
@click.option("--cpu", "cpus", multiple=True, required=True)
@click.option("--gpu", "gpus", multiple=True, required=True)
@click.option("--memory", type=float, required=True)
@click.option("--model", "model_name", required=True)
@click.option("--output", type=click.Choice(["wide", "json"]), default=None)
@click.pass_context
def check(
    ctx: click.Context,
    cpus: tuple[str, ...],
    gpus: tuple[str, ...],
    memory: float,
    model_name: str,
    output: str | None,
) -> None:
    report = ctx.obj["sdk"].check(
        cpu_names=list(cpus),
        gpu_names=list(gpus),
        memory_gb=memory,
        model_name=model_name,
    )
    click.echo(render_score_report(report, output=output or "default"))


def main() -> None:
    cli(obj={})
